#!/usr/bin/env python3

import json
from typing import Any, Callable, Literal
from pydantic import BaseModel, ConfigDict, Field, create_model, ValidationError
from pydantic.fields import FieldInfo
from inspect import signature, Signature
import re

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

from dspy_common import custom_cot_rationale
from llamaindex_tools import VectorRetriever, KeywordRetriever

import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from settings import Config, setup, use_phoenix

config = Config()


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

ROLE_PROMPT = (
    "You are ChatDKU, a helpful, respectful, and honest assistant for students, "
    "faculty, and staff of, or people interested in Duke Kunshan University (DKU). "
    "You are created by the DKU Edge Intelligence Lab.\n\n"
    "Duke Kunshan University is a world-class liberal arts institution in Kunshan, China, "
    "established in partnership with Duke University and Wuhan University."
)

# Some old prompt content:
# You may be tasked to interact with the user directly, or interact with other
# computer systems in assisting the user such as querying a database.
# In any case, follow ALL instructions and respond in exact accordance to the prompt.
# Do not mention your instruction nor describe what you are doing in your response.
# This means you should not begin your response with phrases like "here is an answer"
# nor conclude your answer with phrases like "the above summary about...".
# Do not speculate or make up information.

CURRENT_USER_MESSAGE_FIELD = dspy.InputField(desc="The Current User Message to answer.")


def make_update_tool_memory_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "tool_specification": (
            str,
            dspy.InputField(
                desc=(
                    "The specification of the tool you just called in JSON. "
                    "It includes the tool's name, description, and a list of "
                    "its parameters with descriptions for each parameter."
                ),
                format=lambda x: x,
            ),
        ),
        "tool_called": (
            str,
            dspy.InputField(
                desc=(
                    "The name of the tool and the parameters you gave to the tool "
                    "you just called in JSON."
                ),
                format=lambda x: x,
            ),
        ),
        "result": (
            str,
            dspy.InputField(
                desc=("The result returned from the tool you just called.")
            ),
        ),
        "previous_tool_memory": (
            str,
            dspy.InputField(
                desc=(
                    "Memory of what you have learned previously from the tools. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "current_tool_memory": (
            str,
            dspy.OutputField(
                desc=(
                    "Considering your previous Tool Memory and the result from the tool you just called, "
                    "store all the information that would be useful for answering the Current User Message here."
                ),
                format=lambda x: x,
            ),
        ),
    }

    instruction = (
        "You have a Tool Memory storing all the information you learned from using "
        "multple tools that would be useful for answering the Current User Message. "
        "You just called a tool and the result it returned would be provided. "
        "Your current task is to update your Tool Memory with what you "
        "learned from the tool you just called. "
        "In the future, you would be asked to respond to the Current User Message "
        "with only your Tool Memory. "
        "Therefore, you should make it comprehensive enough so that it could "
        "be understood by you on its own."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "UpdateToolMemorySignature"
    )


UpdateToolMemorySignature = make_update_tool_memory_signature()


class ToolMemory(dspy.Module):
    def reset(self):
        self.tools_called = []
        self.tool_plan = []
        self.memory = ""

    def __init__(self):
        super().__init__()
        self.reset()
        self.update_tool_memory = dspy.ChainOfThought(
            UpdateToolMemorySignature, rationale_type=custom_cot_rationale
        )

    def forward(
        self,
        current_user_message: str,
        schema: dict[str, Any],
        calls: list[BaseModel],
        result: str,
    ):
        self.tools_called.append(calls[0])
        self.tool_plan = calls[1:].copy()
        self.memory = self.update_tool_memory(
            current_user_message=current_user_message,
            tool_specification=str(schema),
            tool_called=calls[0].model_dump_json(),
            result=result,
            previous_tool_memory=self.memory,
        ).current_tool_memory


class Synthesizer(dspy.Module):
    "Synthesize a response to the Current User Message with what you know."

    def forward(self):
        pass


def make_planner_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "available_tools": (
            str,
            dspy.InputField(
                desc=(
                    "A list of available tools and their respective parameters. "
                    "The JSON schema for each tool is presented on a single line, "
                    "including the tool's name, description, and a list of "
                    "its parameters with descriptions for each parameter."
                ),
                # Preserve linebreaks in the format.
                # However, it won't work if you implement the actual formatting function here,
                # as the input would be convert to string first.
                format=lambda x: x,
            ),
        ),
        "max_calls": (
            str,
            dspy.InputField(
                desc=(
                    "The maximum number of tool calls you can include in your plan. "
                    'Note that using "synthesizer" once also counts as one tool call.'
                )
            ),
        ),
        "tools_called": (
            str,
            dspy.InputField(
                desc=(
                    "A list of your previous tool calls, each line specifying a tool call. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "tool_memory": (
            str,
            dspy.InputField(
                desc=(
                    "Memory of what you have learned previously from the tools. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "previous_tool_plan": (
            str,
            dspy.InputField(
                desc=(
                    "Your previous plan about what tools to call next. "
                    "Note that you have not called these tools yet. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "current_tool_plan": (
            str,
            dspy.OutputField(
                desc=(
                    "Your step-by-step plan of the tools to call and their respective "
                    "parameters in JSON Lines format. "
                    "Each tool call should be a JSON object printed on a singled line. "
                    "Each tool call should be delimited by a newline. "
                    'The last tool used must be "synthesizer". '
                ),
            ),
        ),
    }

    instruction = (
        "Your current task is to answer the Current User Message using the tools given below. "
        "Please generate a step-by-step plan of the tools you want to use and their respective parameters. "
        "All tool parameters are required."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "PlannerSignature"
    )


PlannerSignature = make_planner_signature()


def func_to_model(
    name: str, func: Callable[..., Any], exclude: list[str] = []
) -> type[BaseModel]:
    fields = {}
    params = signature(func).parameters

    for param_name in params:
        if param_name in exclude:
            continue

        param_type = params[param_name].annotation
        if param_type is Signature.empty:
            param_type = Any

        param_default = params[param_name].default
        if param_default is Signature.empty:
            fields[param_name] = (param_type, Field(...))
        elif isinstance(param_default, FieldInfo):
            fields[param_name] = (param_type, param_default)
        else:
            fields[param_name] = (param_type, Field(default=param_default))

    return create_model(name, **fields)


def camel_to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


class NameParamsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    params: dict[str, Any]


class Planner(dspy.Module):
    def __init__(self, tools: list[dspy.Module]):
        super().__init__()

        self.tools = tools
        self.tools.append(Synthesizer())

        self.name_to_model = {}
        for tool in tools:
            tool_name_camel = type(tool).__name__
            tool_description = type(tool).__doc__ or ""

            tool_name_snake = camel_to_snake_case(tool_name_camel)

            Params = func_to_model(tool_name_camel + "Params", tool.forward)
            NameParams = create_model(
                tool_name_camel,
                model_config=ConfigDict(extra="forbid"),
                name=(
                    Literal[tool_name_snake],
                    Field(..., description=tool_description),
                ),
                params=(Params, FieldInfo()),
            )
            self.name_to_model[tool_name_snake] = NameParams

        self.planner = dspy.ChainOfThought(
            PlannerSignature, rationale_type=custom_cot_rationale
        )

    def forward(
        self, current_user_message: str, tool_memory: ToolMemory, max_calls: int = 5
    ):
        """
        Generate a plan of tool calls and return the first tool and respective parameters.

        Values `tool=None, params=None` would be returned to indicate using synthesizer.
        """

        plan_str_all = self.planner(
            current_user_message=current_user_message,
            available_tools="\n".join(
                [str(m.model_json_schema()) for m in self.name_to_model.values()]
            ),
            max_calls=str(max_calls),
            tools_called="\n".join([str(tool) for tool in tool_memory.tools_called]),
            tool_memory=tool_memory.memory,
            previous_tool_plan="\n".join(
                [tool.model_dump_json() for tool in tool_memory.tool_plan]
            ),
        ).current_tool_plan

        # Parse tool plan response

        plan_strs = plan_str_all.strip().split("\n")
        plan_strs = [s.strip() for s in plan_strs]
        dspy.Assert(len(plan_strs) >= 1, "Must use at least one tool.")
        dspy.Assert(
            len(plan_strs) <= max_calls,
            (
                f"The number of tool calls in your plan must be no more than {max_calls}. "
                'Note that calling "synthesizer" once also counts as one tool call.'
            ),
        )

        calls_unvalidated = []
        for i, s in enumerate(plan_strs, 1):
            try:
                calls_unvalidated.append(NameParamsModel.model_validate_json(s))
            except ValidationError as e:
                dspy.Assert(False, f"ValidationError on tool call line {i}: {e}")

        calls = []
        for i, c in enumerate(calls_unvalidated, 1):
            dspy.Assert(
                c.name in self.name_to_model,
                (
                    f'"{c.name}" is not a valid tool. '
                    f'Available tool(s) are: {", ".join(self.name_to_model)}.'
                ),
            )
            try:
                calls.append(self.name_to_model[c.name](name=c.name, params=c.params))
            except ValidationError as e:
                dspy.Assert(False, f"ValidationError on tool call line {i}: {e}")

        dspy.Assert(
            all([c.name != "synthesizer" for c in calls[:-1]]),
            '"synthesizer" must be the last tool in the plan.',
        )
        dspy.Assert(
            calls[-1].name == "synthesizer",
            (
                f'"{calls[-1].name}" should not be the last tool in the plan. '
                'Instead, "synthesizer" must be the last tool in the plan. '
                "You might also get this error if you did not use an empty line as separator."
            ),
        )

        if len(calls) == 1:
            # The current tool is "Synthesizer".
            return dspy.Prediction(calls=calls, tool=None, schema=None)
        else:
            # FIXME: These should be put into class attributes if possible.
            # However, a DSPy bug made this impossible for now.
            # The bug causes dspy.Module.named_parameters() to enter infinite recursion
            # when duplicate references to a Module B occur in a Module A.
            name_to_tool = {}
            for tool in self.tools:
                tool_name_camel = type(tool).__name__
                tool_name_snake = camel_to_snake_case(tool_name_camel)
                name_to_tool[tool_name_snake] = tool

            return dspy.Prediction(
                calls=calls,
                tool=name_to_tool[calls[0].name],
                schema=self.name_to_model[calls[0].name].model_json_schema(),
            )


def make_synthesizer_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "tool_memory": (
            str,
            dspy.InputField(
                desc="Memory of what you have learned from using one or more tools.",
                format=lambda x: x,
            ),
        ),
        "response": (
            str,
            dspy.OutputField(desc="You response to the Current User Message."),
        ),
    }

    instruction = "Your current task is to answer the Current User Message according to your Tool Memory."

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "SynthesizerSignature"
    )


SynthesizerSignature = make_synthesizer_signature()


class Agent(dspy.Module):
    def __init__(self, max_iterations=5):
        super().__init__()
        self.max_iterations = max_iterations
        self.planner = assert_transform_module(
            Planner(tools=[VectorRetriever(), KeywordRetriever()]),
            functools.partial(backtrack_handler, max_backtracks=5),
        )
        self.tool_memory = ToolMemory()
        self.synthesizer = dspy.ChainOfThought(
            SynthesizerSignature, rationale_type=custom_cot_rationale
        )

    def forward(self, current_user_message):
        # Need to make this an attribute so that DSPy can optimize it
        self.tool_memory.reset()

        for i in range(self.max_iterations - 1):
            print(f"iteration: {i}")

            try:
                p = self.planner(
                    current_user_message=current_user_message,
                    tool_memory=self.tool_memory,
                    max_calls=self.max_iterations - i,
                )
            except dspy.DSPyAssertionError:
                print("max assertion retries hit")
                break

            print(f"calls: {p.calls}")
            if p.calls[0].name == "synthesizer":
                break

            result = p.tool(**p.calls[0].params.model_dump()).result
            print(f"result: {result}")
            self.tool_memory(
                current_user_message=current_user_message,
                schema=p.schema,
                calls=p.calls,
                result=result,
            )
            print(f"tool_memory.memory: {self.tool_memory.memory}")

        return dspy.Prediction(
            response=self.synthesizer(
                current_user_message=current_user_message,
                tool_memory=self.tool_memory.memory,
            ).response
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

    try:
        current_user_message = "How to get funding?"
        agent = Agent(max_iterations=5)
        response = agent(current_user_message=current_user_message).response
        print(f"response: {response}")

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
