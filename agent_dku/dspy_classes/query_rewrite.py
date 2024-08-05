import dspy
from dspy_common import custom_cot_rationale


class QueryRewriteSignature(dspy.Signature):

    question = dspy.InputField(desc="The question to be answered.")
    known_information = dspy.InputField(
        desc="Known information for replying to the question."
    )
    rewrited_query = dspy.OutputField(
        desc=(
            # 'You serve as an intelligent assistant, adept at facilitating users through complex, multi-hop reasoning across multiple documents.'
            "Please understand the information gap between the currently known information and the target problem."
            "Your task is to generate one thought in the form of question for next retrieval step directly."
            "DON\’T generate the whole thoughts at once!\n DON\’T generate thought which has been retrieved."
            "Answer the thought you generate directly, without additional description."
        )
    )


class QueryRewrite(dspy.Module):
    def __init__(self):
        super().__init__()
        self.rewrited_query = dspy.ChainOfThought(
            QueryRewriteSignature, rationale_type=custom_cot_rationale
        )

    def forward(self, question, known_information):
        rewrited_str = self.rewrited_query(
            question=question, known_information=known_information
        ).rewrited_query
        print(rewrited_str)
        return rewrited_str
