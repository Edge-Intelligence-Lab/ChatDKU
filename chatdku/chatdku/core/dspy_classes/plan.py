from typing import Any, Literal

import dspy
from dspy import Tool
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import OpenInferenceSpanKindValues as SpanKind

from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.prompt_settings import (
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
)
from chatdku.core.dspy_common import get_template
from chatdku.core.utils import (
    span_ctx_start,
    token_limit_ratio_to_count,
    truncate_tokens_all,
)


class PlannerSignature(dspy.Signature):
    """
    You are a Planner Agent for Duke Kunshan University (DKU). In each episode, you are given available tools.
    And you can see your past trajectory so far. Your goal is to use one or more of the
    supplied tools to collect any necessary information for answering the user's question.
    To do this, you will produce next_thought, next tool name, and next tool args in each turn,
    and also when finishing the task.
    After each tool call, you receive a resulting observation, which gets appended to your trajectory.
    When writing next_thought, you may reason about the current situation and plan for future steps.
    When selecting the next_tool_name and its next_tool_args, the tool must be one of the provided tools.

    The user's question might be complex and require multiple hops of tool calls. If it is complex,
    break down the question into small tool calls to get whatever information you need to answer.
    """

    current_user_message: str = dspy.InputField()
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD


class Planner(dspy.Module):
    def __init__(self, tools):
        super().__init__()
        tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
        tools = {tool.name: tool for tool in tools}

        instr = (
            [f"{PlannerSignature.instructions}\n"]
            if PlannerSignature.instructions
            else []
        )

        tools["finish"] = Tool(
            func=lambda: "Completed.",
            name="finish",
            desc=(
                "Marks the task as complete. That is, signals that all information"
                " for asnwering the current_user_message are now available to be extracted."
            ),
            args={},
        )

        for idx, tool in enumerate(tools.values()):
            instr.append(f"({idx + 1}) {tool}")
        instr.append(
            "When providing `next_tool_args`, the value inside the field must be in JSON format"
        )

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
        self.planner = dspy.Predict(react_signature)
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 3 / 15,
            "conversation_summary": 1 / 15,
            "trajectory": 6 / 15,
        }

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.planner, **kwargs))
        return token_limit_ratio_to_count(self.token_ratios, template_len)

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        max_calls: int = 5,
    ) -> dspy.Prediction:
        planner_inputs = dict(
            current_user_message=current_user_message,
            conversation_history=conversation_memory.history_str(),
            conversation_summary=conversation_memory.summary,
        )

        trajectory = {}
        with span_ctx_start("Planner", SpanKind.AGENT) as span:
            span.set_attribute("agent.name", "Planner")
            span.set_attribute("input.value", safe_json_dumps(planner_inputs))

            # Tool calling iterations
            for idx in range(max_calls):
                planner_inputs["trajectory"] = format_trajectory(trajectory)
                planner_inputs = truncate_tokens_all(
                    planner_inputs,
                    self.get_token_limits(**planner_inputs),
                )

                plan = self.planner(**planner_inputs)

                trajectory[f"thought_{idx}"] = plan.next_thought
                trajectory[f"tool_name_{idx}"] = plan.next_tool_name
                trajectory[f"tool_args_{idx}"] = plan.next_tool_args

                try:
                    trajectory[f"observation_{idx}"] = self.tools[plan.next_tool_name](
                        **plan.next_tool_args
                    )
                except Exception as err:
                    trajectory[f"observation_{idx}"] = (
                        f"Execution error in {plan.next_tool_name}: {_fmt_exc(err)}"
                    )
                if plan.next_tool_name == "finish":
                    break
            span.set_attribute("output.value", safe_json_dumps(trajectory))
        return dspy.Prediction(trajectory=format_trajectory(trajectory))


# From the DSPY.react code
# https://github.com/stanfordnlp/dspy/blob/bb110a0262f2373150d864792bcc92e76f43cd62/dspy/predict/react.py#L91-L94
def format_trajectory(trajectory: dict[str, Any]):
    adapter = dspy.settings.adapter or dspy.ChatAdapter()
    trajectory_signature = dspy.Signature(f"{', '.join(trajectory.keys())} -> x")
    return adapter.format_user_message_content(trajectory_signature, trajectory)


def _fmt_exc(err: BaseException, *, limit: int = 5) -> str:
    """
    Return a one-string traceback summary.
    * `limit` - how many stack frames to keep (from the innermost outwards).
    """

    import traceback

    return (
        "\n"
        + "".join(
            traceback.format_exception(type(err), err, err.__traceback__, limit=limit)
        ).strip()
    )
