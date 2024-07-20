#!/usr/bin/env python3

import json
from typing import Any
from llama_index.core import VectorStoreIndex
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever

from llama_index.core import Settings
from llama_index.core.base.llms.types import CompletionResponse

import functools
from dsp import LM
import dspy
import dsp
from dspy.teleprompt import BootstrapFewShot
from dspy.evaluate import Evaluate
from dspy.primitives.assertions import assert_transform_module, backtrack_handler
from dspy import Predict
from dspy.signatures.signature import ensure_signature, signature_to_template

# FIXME: Stop using these patches whenever the issues were addressed by DSPy.
import dspy_patch

from settings import setup, use_phoenix
from config import Config

config = Config()

import llama_index


def mydeepcopy(self, memo):
    return self


# FIXME: Ugly hack for the issue that DSPy's use of `deepcopy()` cannot copy
# certain attributes (probably due to the being Pydantic `PrivateAttr()`?)
llama_index.vector_stores.chroma.ChromaVectorStore.__deepcopy__ = mydeepcopy


class CustomClient(LM):
    def __init__(self) -> None:
        self.provider = "default"
        self.history = []
        self.kwargs = {
            "temperature": Settings.llm.temperature,
            "max_tokens": Settings.llm.context_window,
        }

    def basic_request(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        response = Settings.llm.complete(prompt, **kwargs)
        self.history.append(
            {
                "prompt": prompt,
                "response": response,
                "kwargs": kwargs,
            }
        )
        return response

    def inspect_history(self, n: int = 1, skip: int = 0) -> str:
        last_prompt = None
        printed = []
        n = n + skip

        for x in reversed(self.history[-100:]):
            prompt = x["prompt"]
            if prompt != last_prompt:
                printed.append((prompt, x["response"].text))
            last_prompt = prompt
            if len(printed) >= n:
                break

        printing_value = ""
        for idx, (prompt, text) in enumerate(reversed(printed)):
            # skip the first `skip` prompts
            if (n - idx - 1) < skip:
                continue
            printing_value += "\n\n\n"
            printing_value += prompt
            printing_value += self.print_green(text, end="")
            printing_value += "\n\n\n"

        print(printing_value)
        return printing_value

    def __call__(
        self,
        prompt: str,
        only_completed: bool = True,
        return_sorted: bool = False,
        **kwargs: Any,
    ) -> list[str]:
        return [self.request(prompt, **kwargs).text]


def get_template(predict_module: Predict) -> str:
    """Get formatted template from predict module."""
    """Adapted from https://github.com/stanfordnlp/dspy/blob/55510eec1b83fa77f368e191a363c150df8c5b02/dspy/predict/llamaindex.py#L22-L36"""
    # Extract the three privileged keyword arguments.
    signature = ensure_signature(predict_module.signature)
    # Switch to legacy format for dsp.generate
    template = signature_to_template(signature)

    if hasattr(predict_module, "demos"):
        demos = predict_module.demos
    else:
        demos = []
    # All of the other kwargs are presumed to fit a prefix of the signature.
    # That is, they are input variables for the bottom most generation, so
    # we place them inside the input - x - together with the demos.
    x = dsp.Example(demos=demos)
    return template(x)


custom_cot_rationale = dspy.OutputField(
    prefix="Rationale:",
    desc="The step-by-step rationale of how you derive the response.",
)


class DocumentSummarizerSignature(dspy.Signature):
    """Update the summary with information in the documents that are relevant to the query."""

    previous_summary = dspy.InputField(
        desc="The previously generated summary of relevant information. May be empty."
    )
    documents = dspy.InputField(
        desc="The documents to extract relevant information from."
    )
    query = dspy.InputField(desc="The query that the summary should answer.")
    current_summary = dspy.OutputField(
        desc="The combined summary of relevant information in Previous Summary and Documents."
    )


class DocumentSummarizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarizer = dspy.ChainOfThought(
            DocumentSummarizerSignature, rationale_type=custom_cot_rationale
        )

    def forward(self, documents, query):
        summary = ""
        for doc in documents:
            summary = self.summarizer(
                previous_summary=summary, documents=doc, query=query
            ).current_summary
        return dspy.Prediction(summary=summary)


class Tool(dspy.Module):
    def __init__(self, name: str, desc: str, param_specs: dict[str, str]):
        super().__init__()
        self.name = name
        self.desc = desc
        self.param_specs = param_specs


class VectorRetriever(Tool):
    def __init__(self, top_k: int = 5):
        super().__init__(
            "Vector Retriever",
            "Retrieve texts from the database that are semantically similar to the query.",
            {
                "Query": "Texts that might be semantically similar to the real answer to the question."
            },
        )
        db = chromadb.PersistentClient(path=config.chroma_db)
        chroma_collection = db.get_or_create_collection("dku_html_pdf")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        self.retriever = index.as_retriever(similarity_top_k=top_k)
        self.summarizer = DocumentSummarizer()

    def forward(self, params: dict[str, str]):
        query = params["Query"]
        nodes = self.retriever.retrieve(query)
        texts = [node.get_content() for node in nodes]
        return self.summarizer(documents=texts, query=query)


class KeywordRetriever(Tool):
    def __init__(self, top_k: int = 5):
        super().__init__(
            "Keyword Retriever",
            "Retrieve texts from the database that contain the same keywords in the query.",
            {"Query": "Keywords that might appear in the answer to the question."},
        )
        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        self.retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=top_k
        )
        self.summarizer = DocumentSummarizer()

    def forward(self, params: dict[str, str]):
        query = params["Query"]
        nodes = self.retriever.retrieve(query)
        texts = [node.get_content() for node in nodes]
        return self.summarizer(documents=texts, query=query)


# When executing tasks like summarizing, the LLM is supposed to ONLY generate the
# summaries themselves. However, the LLM sometimes says things like
# `here is a summary of the given text` before the summary. This prompt used to
# explicitly discourage this kind of output.
#
# Also note that I have tried other things like `do not begin your answer with
# "here are the generated queries"` to discourage such messages at the beginning of
# the generated queries. Nevertheless, this prompt seems to be the most effective.
#
# FIXME: Use a more suitable system prompt
class PlanSignature(dspy.Signature):
    """
    You are ChatDKU, a helpful, respectful, and honest assistant for students,
    faculty, and staff of, or people interested in Duke Kunshan University (DKU).
    You are created by the DKU Edge Intelligence Lab.

    Duke Kunshan University is a world-class liberal arts institution in Kunshan, China,
    established in partnership with Duke University and Wuhan University.
    You may be tasked to interact with the user directly, or interact with other
    computer systems in assisting the user such as querying a database.
    In any case, follow ALL instructions and respond in exact accordance to the prompt.
    Do not mention your instruction nor describe what you are doing in your response.
    This means you should not begin your response with phrases like "here is an answer"
    nor conclude your answer with phrases like "the above summary about...".
    Do not speculate or make up information.

    Your current task is to answer the current user message using the tools given below.
    Please generate a step-by-step plan of the tools you want to use and their respective parameters.
    All tool parameters are required.
    Note that a special tool named "Synthesizer" (without quotes) must be used
    at the end to synthesize a final response to the user.
    It has no parameters and would not be explicitly given below.
    """

    current_user_message = dspy.InputField(desc="The current user message to answer.")
    available_tools = dspy.InputField(
        desc=(
            "A list of available tools and their respective parameters. "
            "For each tool, its name, description, a list of its parameter(s) "
            "(including the description of each parameter) is given."
        ),
        # Preserve linebreaks in the format.
        # However, it won't work if you implement the actual formatting function here,
        # as the input would be convert to string first.
        format=lambda x: x,
    )
    tool_plan = dspy.OutputField(
        desc=(
            "Your step-by-step plan of the tools to use and their respective parameters. "
            "Output a list of tool usages separated by an empty line. "
            'The last tool used must be "Synthesizer" (without quotes). '
            "For each tool usage, output the name of the tool on the first line. "
            'On the subsequent lines, output the parameters in the format of "Parameter Name: Parameter Value" '
            "(without quotes and you should substitute in the actual parameter names and values)."
        ),
    )


class Plan(dspy.Module):
    def __init__(self, tools: list[Tool]):
        super().__init__()
        self.tools = tools
        self.plan = dspy.ChainOfThought(
            PlanSignature, rationale_type=custom_cot_rationale
        )

    def forward(self, current_user_message):
        """
        Generate a plan of tool calls and return the first tool and respective parameters.

        Values `tool=None, params=None` would be returned to indicate using synthesizer.
        """

        # Format the list of available tools
        at = ""
        for i, tool in enumerate(self.tools):
            at += f"- Tool {i}\n"
            at += f"  - Name: {tool.name}\n"
            at += f"  - Description: {tool.desc}\n"
            if tool.param_specs:
                at += "  - Parameters:\n"
                for j, (pn, pd) in enumerate(tool.param_specs.items()):
                    at += f"    - Parameter {j}\n"
                    at += f"      - Name: {pn}\n"
                    at += f"      - Description: {pd}\n"
            at += "\n"

        plan_str_all = self.plan(
            current_user_message=current_user_message, available_tools=at
        ).tool_plan

        # Parse tool plan response

        # FIXME: These should be put into class attributes if possible.
        # However, a DSPy bug made this impossible for now.
        # The bug causes dspy.Module.named_parameters() to enter infinite recursion
        # when duplicate references to a Module B occur in a Module A.
        name_tools = {tool.name: tool for tool in self.tools}
        name_params = {tool.name: tool.param_specs.keys() for tool in self.tools}
        available_tools_str = ", ".join(
            [f'"{tool.name}"' for tool in self.tools] + ['"Synthesizer"']
        )
        available_params_str = {
            name: ", ".join([f'"{p}"' for p in params])
            for name, params in name_params.items()
        }

        plan_strs = plan_str_all.strip().split("\n\n")
        dspy.Assert(len(plan_strs) >= 1, "Must use at least one tool.")

        plan_strs = [s.strip() for s in plan_strs]
        dspy.Assert(
            plan_strs[-1] == "Synthesizer",
            '"Synthesizer" (without quotes) must be the last tool in the plan.',
        )
        if len(plan_strs) == 1:
            # The current tool is "Synthesizer".
            return dspy.Prediction(tool_plan=plan_str_all, tool=None, params=None)

        first_tool = True
        for s in plan_strs[:-1]:
            lines = s.split("\n")
            lines = [line.strip() for line in lines]

            name = lines[0]
            dspy.Assert(
                len(name) >= 1,
                (
                    "Empty tool usage specification. "
                    "There should be no more than one consective empty line in the plan."
                ),
            )
            dspy.Assert(
                name != "Synthesizer",
                '"Synthesizer" (without quotes) must be the last tool in the plan.',
            )
            dspy.Assert(
                name in name_params.keys(),
                (
                    f'"{name}" is not a valid tool. '
                    f"Available tools are: {available_tools_str} (without quotes and case-sensitive)."
                ),
            )

            params = {}
            for line in lines[1:]:
                parts = line.split(":", 1)
                dspy.Assert(
                    len(parts) == 2,
                    "There must at least one colon on each line specifying"
                    'a "Parameter Name: Parameter Value" (without quotes) pair.',
                )

                parts = [part.strip() for part in parts]
                p_name, p_value = parts[0], parts[1]
                dspy.Assert(
                    p_name in name_params[name],
                    (
                        f'"{p_name}" is not a valid parameter name. '
                        f"Available parameter names are: {available_params_str[name]} (without quotes and case-sensitive)."
                    ),
                )
                params[p_name] = p_value

            for p_name in name_params[name]:
                dspy.Assert(
                    p_name in params,
                    (
                        f'"{p_name}" is missing from the tool usage specification. '
                        f"Note that all parameters of the tools are required."
                    ),
                )

            if first_tool:
                first_tool = False
                first_name = name
                first_params = params

        print(plan_str_all)
        print(first_name)
        print(first_params)

        return dspy.Prediction(
            tool_plan=plan_str_all,
            tool=name_tools[first_name],
            params=first_params,
        )


class JudgeSignature(dspy.Signature):
    """Judge if the current answer is equivalent to the ground truth answer to the question."""

    question = dspy.InputField(desc="The question to be answered.")
    ground_truth = dspy.InputField(desc="The ground truth answer to the question.")
    answer = dspy.InputField(desc="The current answer to be judged.")
    judgement = dspy.OutputField(
        desc='Whether the current answer is equivalent to the ground truth ("True" or "False").'
    )


class Judge(dspy.Module):
    def __init__(self):
        super().__init__()
        self.judge = dspy.TypedChainOfThought(
            JudgeSignature, reasoning=custom_cot_rationale
        )

    def forward(self, question, ground_truth, answer):
        judgement_str = self.judge(
            question=question, ground_truth=ground_truth, answer=answer
        ).judgement
        dspy.Suggest(
            judgement_str in ["True", "False"],
            'Judgement should be either "True" or "False" (without quotes and first letter of each word capitalized).',
        )
        return dspy.Prediction(judgement=(judgement_str == "True"))


def main():
    setup()
    use_phoenix()

    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)

    plan = assert_transform_module(
        Plan(tools=[VectorRetriever(), KeywordRetriever()]),
        functools.partial(backtrack_handler, max_backtracks=5),
    )

    try:
        print(plan.forward(current_user_message="How to get funding?"))
    except Exception as e:
        print(e)

    input()

    # file_path = "../datasets/before_RAG_dataset.json"
    # with open(file_path, "r", encoding="utf-8") as file:
    #     json_data = json.load(file)
    # dataset = [
    #     dspy.Example(question=d["question"], answer=d["ground_truth"]).with_inputs(
    #         "question"
    #     )
    #     for d in json_data
    # ]

    # trainset, devset = dataset[50:51], dataset[60:61]

    # judge = assert_transform_module(
    #     Judge(),
    #     functools.partial(backtrack_handler, max_backtracks=3),
    # )

    # def metric(example, pred, trace=None):
    #     prediction = judge(
    #         question=example.question, ground_truth=example.answer, answer=pred.answer
    #     )
    #     return prediction.judgement

    # config = dict(max_bootstrapped_demos=1, max_labeled_demos=0, max_errors=1)
    # teleprompter = BootstrapFewShot(metric=metric, **config)

    # # try:

    # rag = assert_transform_module(
    #     Rag(vector_top_k=5, keyword_top_k=5),
    #     functools.partial(backtrack_handler, max_backtracks=3),
    # )
    # rag = teleprompter.compile(rag, trainset=trainset)
    # # except:
    # #     input()

    # rag.save("compiled_rag.json")

    # # Set up the evaluator, which can be used multiple times.
    # evaluate = Evaluate(
    #     devset=devset,
    #     metric=metric,
    #     num_threads=1,  # Multi-threading won't work for our local model
    #     display_progress=True,
    #     display_table=True,
    # )

    # # Evaluate our `optimized_cot` program.
    # evaluate(rag)

    # print(llama_client.inspect_history(n=1))

    # input()

    # while True:
    #     try:
    #         print("*" * 32)
    #         query = input("> ")
    #         output = pipeline.run(input=query)
    #         print("+" * 32)
    #         print(output)
    #     except EOFError:
    #         break


if __name__ == "__main__":
    main()
