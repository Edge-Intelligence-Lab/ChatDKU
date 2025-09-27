import dspy
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.dspy_common import get_template
from chatdku.core.utils import token_limit_ratio_to_count


class PlannerSignature(dspy.Signature):
    "Plan the appropiate tool calls to answer the given user question."

    current_user_message: str = dspy.InputField()
    max_calls: int = dspy.InputField()
    tools: list[dspy.Tool] = dspy.InputField()
    tool_history: str = dspy.InputField(
        desc= "Your previous tool calls in JSON Lines format. "
        "It would be empty if you have not called any tools previously."
    )
    previous_tool_plan: dspy.ToolCalls = dspy.InputField()
    conversation_history: dspy.History = dspy.InputField()

    tool_plan: dspy.ToolCalls = dspy.OutputField()


class Planner(dspy.Module):
    def __init__(self):
        super().__init__()
        self.planner = dspy.ChainOfThought(PlannerSignature)
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 2 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
            "previous_tool_plan": 1 / 15,
        }

    def get_token_limits(self, tools: list[dspy.Tool]) -> dict[str, int]:
        template_len = len(
            get_template(
                self.planner,
                tools = tools,
                max_calls=str(1),
            )
        )
        return token_limit_ratio_to_count(self.token_ratios, template_len)

    def forward(
        self,
        current_user_message: str, 
        tools: list[dspy.Tool],
        conversation_history: dspy.History,
        tool_memory: ToolMemory,
        max_calls: int = 5,
    ) -> dspy.Prediction:

        planner = self.planner(
            current_user_message=current_user_message,
            max_calls=max_calls,
            tools=tools,
            tool_history = tool_memory.history_str(),
            previous_tool_plan = tool_memory.plan,
            conversation_history = conversation_history
        )

        tool_plan = planner.tool_plan

        return dspy.Prediction(tool_plan=tool_plan)

    async def aforward(
        self,
        current_user_message: str,
        tools: list[dspy.Tool],
        conversation_history: dspy.History,
        tool_memory: ToolMemory,
        max_calls: int = 5,
    ) -> dspy.Prediction:

        planner = await self.planner.acall(
            current_user_message=current_user_message,
            max_calls=max_calls,
            tools=tools,
            tool_history=tool_memory.history_str(),
            previous_tool_plan=tool_memory.plan,
            conversation_history=conversation_history,
        )

        return dspy.Prediction(tool_plan=planner.tool_plan)
