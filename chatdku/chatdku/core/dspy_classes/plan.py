from typing import Any, Literal

import dspy
from dspy import Tool

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
    You are a Planner Agent. In each episode, you are given available tools.
    And you can see your past trajectory so far. Your goal is to use one or more of the
    supplied tools to collect any necessary information for answering the user's question.
    To do this, you will produce next_thought, next tool name, and next tool args in each turn,
    and also when finishing the task.
    After each tool call, you receive a resulting observation, which gets appended to your trajectory.
    When writing next_thought, you may reason about the current situation and plan for future steps.
    When selecting the next_tool_name and its next_tool_args, the tool must be one of the provided tools.
    """

    current_user_message: str = dspy.InputField()
    conversation_history: str = CONVERSATION_HISTORY_FIELD


class Planner(dspy.Module):
    def __init__(self, tools: list):
        super().__init__()
        tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
        tools = {tool.name: tool for tool in tools}

        instr = (
            [f"{PlannerSignature.instructions}\n"]
            if PlannerSignature.instructions
            else []
        )

        outputs = ", ".join([f"`{k}`" for k in PlannerSignature.output_fields.keys()])

        tools["finish"] = Tool(
            func=lambda: "Completed.",
            name="finish",
            desc=(
                "Marks the task as complete. That is, signals that all information"
                f" for producing the outputs, i.e. {outputs}, are now available to be extracted."
            ),
            args={},
        )

        for idx, tool in enumerate(tools.values()):
            instr.append(f"({idx + 1}) {tool}")
        instr.append(
            "When providing `next_tool_args`, the value inside the field must be in JSON format"
        )

        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 3 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
        }
        react_signature = (
            dspy.Signature({**PlannerSignature.input_fields}, "\n".join(instr))
            .append("trajectory", dspy.InputField(), type_=str)
            .append("next_thought", dspy.OutputField(), type_=str)
            .append(
                "next_tool_name", dspy.OutputField(), type_=Literal[tuple(tools.keys())]
            )
            .append("next_tool_args", dspy.OutputField(), type_=dict[str, Any])
        )

        self.tools = tools
        self.planner = dspy.Predict(PlannerSignature)

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
