import dspy
from dspy_common import custom_cot_rationale
from dspy_classes.prompt_settings import VERBOSE


class JudgeSignature(dspy.Signature):
    """Judging based solely on the current known information and without allowing for inference, \
    are you able to completely and accurately respond to the question?
    """

    question = dspy.InputField(desc="The question to be answered.")
    known_information = dspy.InputField(
        desc="Known information for replying to the question."
    )
    judgement = dspy.OutputField(
        desc=(
            'If you can answer the question, please reply with "Yes" directly; '
            'if you cannot and need more information, please reply with "No" directly.'
        )
    )


class Judge(dspy.Module):
    def __init__(self):
        super().__init__()
        self.judge = dspy.ChainOfThought(
            JudgeSignature, rationale_type=custom_cot_rationale
        )

    def forward(self, question, known_information):
        judgement_str = self.judge(
            question=question, known_information=known_information
        ).judgement
        dspy.Suggest(
            judgement_str in ["Yes", "No"],
            'Judgement should be either "Yes" or "No" (without quotes and first letter of each word capitalized).',
        )
        if judgement_str not in ["Yes", "No"]:
            if VERBOSE:
                print(
                    'Judgement not "Yes" or "No" after retries, default to "No" (`False`).'
                )
        return dspy.Prediction(judgement=(judgement_str == "Yes"))
