import dspy
from utils import token_limit_ratio_to_count, truncate_tokens_all
from dspy_common import get_template, custom_cot_rationale
from dspy_classes.conversation_memory import ConversationMemory
from dspy_classes.tool_memory import ToolMemory
from dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
    ROLE_PROMPT,
)


def make_query_rewrite_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "conversation_history": (str, CONVERSATION_HISTORY_FIELD),
        "conversation_summary": (str, CONVERSATION_SUMMARY_FIELD),
        "tool_history": (str, TOOL_HISTORY_FIELD),
        "tool_summary": (str, TOOL_SUMMARY_FIELD),
        "rewritten_query": (
            str,
            dspy.OutputField(desc="The thought you generated."),
        ),
    }

    instruction = (
        # 'You serve as an intelligent assistant, adept at facilitating users through complex, multi-hop reasoning across multiple documents.'
        "You goal is to answer the Current User Message. "
        "Please understand the information gap between the currently known information and the target problem. "
        "Your task is to generate one thought in the form of question for next retrieval step directly. "
        "DON\’T generate the whole thoughts at once!\n DON\’T generate thought which has been retrieved. "
        "Answer the thought you generate directly, without additional description."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "QueryRewriteSignature"
    )


QueryRewriteSignature = make_query_rewrite_signature()


class QueryRewrite(dspy.Module):
    def __init__(self):
        super().__init__()
        self.rewritten_query = dspy.ChainOfThought(
            QueryRewriteSignature, rationale_type=custom_cot_rationale
        )
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 2 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
        }

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.rewritten_query))
        )

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
    ):
        rewrite_inputs = dict(
            current_user_message=current_user_message,
            conversation_history="\n".join(
                [i.model_dump_json() for i in conversation_memory.history]
            ),
            conversation_summary=conversation_memory.summary,
            tool_history="\n".join([i.model_dump_json() for i in tool_memory.history]),
            tool_summary=tool_memory.summary,
        )
        rewrite_inputs = truncate_tokens_all(rewrite_inputs, self.get_token_limits())
        rewritten_query = self.rewritten_query(**rewrite_inputs).rewritten_query
        print(rewritten_query)
        return dspy.Prediction(rewritten_query=rewritten_query)
