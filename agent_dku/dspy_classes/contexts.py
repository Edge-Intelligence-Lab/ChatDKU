import dspy
from dspy_common import custom_cot_rationale


class ContextsMemorySignature(dspy.Signature):

    question = dspy.InputField(desc="The question to be answered.")
    retrieved_information = dspy.InputField(
        desc="The information related to the question retrieved in the database, some redundant information existed."
    )
    summarized_information = dspy.OutputField(
        desc=(
            # 'The information retrieved from the database has a lot of redundant information.'
            # 'Your task is to compress the retrieved_information in order to better answer the question.'
            # "Here's what you should do:"
            # 'Save information about the question.'
            # 'Save the sources of all contexts referenced, include links in Markdown if availble.'
            # 'Be organized and use bullet points if needed.'
            "Your task is to remove the information that is not relevant to the question in the retrieved information."
            "Please keep the information related to the question as much as possible."
            "keep the source stored in markdown."
        )
    )


class Contexts(dspy.Module):
    def reset(self):
        self.memory = ""

    def __init__(self):
        super().__init__()
        self.reset()
        self.update_context_memory = dspy.ChainOfThought(
            ContextsMemorySignature, rationale_type=custom_cot_rationale
        )

    def forward(
        self,
        current_user_message: str,
        result: str,
    ):
        self.memory += (
            "##########\n"
            + self.update_context_memory(
                question=current_user_message, retrieved_information=result
            ).summarized_information
        )
