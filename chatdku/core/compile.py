#!/usr/bin/env python3
"""Script for DSPy to compile (auto-optimize) our Agent module, then save the
optimized prompts in a JSON file.
"""

import json
import functools
import traceback
import dspy
from dspy.teleprompt import BootstrapFewShot, MIPROv2
from dspy.evaluate import Evaluate
from dspy.primitives.assertions import assert_transform_module, backtrack_handler

from dspy_common import custom_cot_rationale
from agent import CustomClient, Agent

from chatdku.config import config
from chatdku.setup import setup, use_phoenix


class QualityJudgeSignature(dspy.Signature):
    """Judge if the current answer is of the same quality or better when compared
    to the ground truth answer to the question.
    """

    question = dspy.InputField(desc="The question to be answered.")
    ground_truth = dspy.InputField(desc="The ground truth answer to the question.")
    answer = dspy.InputField(desc="The current answer to be judged.")
    judgement = dspy.OutputField(
        desc='Whether the current answer is of good quality compared to the ground truth ("True" or "False").'
    )


class QualityJudge(dspy.Module):
    def __init__(self):
        super().__init__()
        self.judge = dspy.ChainOfThought(
            QualityJudgeSignature, rationale_type=custom_cot_rationale
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

    # Load the dataset here

    file_path = "../datasets/before_RAG_dataset.json"
    with open(file_path, "r", encoding="utf-8") as file:
        json_data = json.load(file)
    dataset = [
        dspy.Example(
            current_user_message=d["question"], answer=d["ground_truth"]
        ).with_inputs("current_user_message")
        for d in json_data
    ]

    trainset, devset = dataset[50:51], dataset[60:61]

    quality_judge = assert_transform_module(
        QualityJudge(),
        functools.partial(backtrack_handler, max_backtracks=3),
    )

    agent = Agent(max_iterations=5)
    agent.save("agent_not_compiled.json")
    # print(agent(current_user_message="Who is Scot MacEachern?"))
    # return

    def metric(example, pred, trace=None):
        return True
        prediction = quality_judge(
            question=example.current_user_message,
            ground_truth=example.answer,
            answer=pred.response,
        )
        return prediction.judgement

    teleprompter = BootstrapFewShot(
        metric=metric, max_bootstrapped_demos=2, max_labeled_demos=0
    )
    agent_compiled = teleprompter.compile(agent, trainset=trainset)

    # MIPROv2 doesn't appear to work now.
    # It makes a lot of weird SQL requests?
    # teleprompter = MIPROv2(
    #     prompt_model=llama_client,
    #     task_model=llama_client,
    #     metric=metric,
    #     num_candidates=5,
    #     log_dir="compilation_logs",
    # )
    # agent_compiled = teleprompter.compile(
    #     agent,
    #     trainset=trainset,
    #     max_bootstrapped_demos=2,
    #     max_labeled_demos=0,
    #     num_batches=3,
    # )

    agent_compiled.save("agent_compiled.json")

    evaluate = Evaluate(
        devset=devset,
        metric=metric,
        num_threads=1,  # I think we can use multiple threads now
        display_progress=True,
        display_table=True,
    )

    evaluate(agent_compiled)

    print(llama_client.inspect_history(n=1))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

    input()
