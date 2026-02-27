import dspy

from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.prompt_settings import (
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
)
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.dspy_common import get_template
from chatdku.core.utils import token_limit_ratio_to_count, truncate_tokens_all


class PlannerSignature(dspy.Signature):
    """
    Plan the appropiate tool calls to answer the given user question.
    The question may be complex and require multiple-hops of tools with different kinds of parameters.
    """

    current_user_message: str = dspy.InputField()
    max_calls: int = dspy.InputField()
    tools: list[dspy.Tool] = dspy.InputField()
    tool_history: str = TOOL_HISTORY_FIELD
    tool_summary: str = TOOL_SUMMARY_FIELD
    previous_tool_plan: list[dspy.ToolCalls.ToolCall] = dspy.InputField(
        desc="The tool plans you previously planned."
    )
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD

    tool_plan: dspy.ToolCalls = dspy.OutputField()


class Planner(dspy.Module):
    def __init__(self):
        super().__init__()
        self.planner = dspy.ChainOfThought(PlannerSignature)
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 3 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
        }

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.planner, **kwargs))
        return token_limit_ratio_to_count(self.token_ratios, template_len)

    def forward(
        self,
        current_user_message: str,
        tools: dict[str, dspy.Tool],
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
        max_calls: int = 5,
    ) -> dspy.Prediction:

        planner_inputs = dict(
            current_user_message=current_user_message,
            tool_history=tool_memory.history_str(),
            tool_summary=tool_memory.summary,
            conversation_history=conversation_memory.history_str(),
            conversation_summary=conversation_memory.summary,
        )

        planner_inputs = truncate_tokens_all(
            planner_inputs,
            self.get_token_limits(
                current_user_message=current_user_message,
                tool_history=tool_memory.history_str(),
                tool_summary=tool_memory.summary,
                previous_tool_plan=str(tool_memory.plan),
                conversation_history=conversation_memory.history_str(),
                conversation_summary=conversation_memory.summary,
                tools=str(list(tools.values())),
                max_calls=str(2),
            ),
        )

        # Function to check whether the planner output is valid
        def _check_errors(args, pred: dspy.Prediction) -> float:
            score = 1.0
            output = pred.tool_plan
            for tool in output.tool_calls:
                if tool.name not in tools:
                    score = -0.1
                    print(
                        f'"{tool.name}" is not a valid tool. Available tools are: {list(tools.values())}'
                    )
            return score

        refined_planner = dspy.Refine(
            self.planner, N=3, reward_fn=_check_errors, threshold=1.0
        )

        planner = refined_planner(
            max_calls=max_calls,
            tools=list(tools.values()),
            previous_tool_plan=tool_memory.plan,
            **planner_inputs,
        )

        tool_plan = planner.tool_plan

        return dspy.Prediction(tool_plan=tool_plan)

    # TODO: async forward needs error checking
    async def aforward(
        self,
        current_user_message: str,
        tools: dict[str, dspy.Tool],
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
        max_calls: int = 5,
    ) -> dspy.Prediction:

        planner = await self.planner.acall(
            current_user_message=current_user_message,
            max_calls=max_calls,
            tools=list(tools.value()),
            tool_history=tool_memory.history_str(),
            tool_summary=tool_memory.summary,
            previous_tool_plan=tool_memory.plan,
            conversation_history=conversation_memory.history_str(),
            conversation_summary=conversation_memory.summary,
        )

        return dspy.Prediction(tool_plan=planner.tool_plan)
