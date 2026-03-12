from typing import Any, Literal

import dspy
from dspy import Tool
from litellm.exceptions import ContextWindowExceededError
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import OpenInferenceSpanKindValues as SpanKind

from chatdku.core.dspy_classes.prompt_settings import (
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    ROLE_PROMPT,
    role_str,
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

    Useful facts:
        - Available subject codes: DKU, GERMAN, INDSTU, JAPANESE, KOREAN, MUSIC, SPANISH,
            ARHU, ARTS, BEHAVSCI, BIOL, CHEM, CHINESE, COMPDSGN, COMPSCI, CULANTH, CULMOVE,
            CULSOC, EAP, ECON, ENVIR, ETHLDR, GCHINA, GCULS, GLHLTH, HIST, HUM, INFOSCI,
            INSTGOV, LIT, MATH, MATSCI, MEDIA, MEDIART, NEUROSCI, PHIL, PHYS, PHYSEDU,
            POLECON, POLSCI, PPE, PSYCH, PUBPOL, SOCIOL, SOSC, STATS, USTUD, WOC, RELIG,
            MINITERM
    """

    current_user_message: str = dspy.InputField()
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD
    chatbot_role: str = ROLE_PROMPT


class SummarizerSignature(dspy.Signature):
    """
    You have a Tool History storing all the tool calls you made for answering the Current User Message.
    Your Tool History has become too long, so the oldest entries have to be discarded.
    You keep a Summary of the discarded tool history.
    Given the History To Discard and Previous Summary, update the Summary.
    Remove the information not relevant to answer the Current User Message
    and keep all the relevant information if possible.
    Use Markdown in Summary.
    """

    # "Store the sources that you retrieved these information from."
    current_user_message: str = dspy.InputField()
    trajectory_to_discard: str = dspy.InputField(
        desc=(
            "The tool calls that would be removed from Tool History"
            "You should extract relevant information from these tool calls."
        ),
    )

    previous_summary: str = dspy.InputField()

    new_summary: str = dspy.OutputField()


def create_react_signature(signature: dspy.Signature, tools: list[Tool]):
    """Create a react signature for the given signature and tools."""
    tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
    tool_dict = {tool.name: tool for tool in tools}

    instr = [f"{signature.instructions}\n"] if signature.instructions else []

    tool_dict["finish"] = Tool(
        func=lambda: "Completed.",
        name="finish",
        desc=("Marks the task as complete."),
        args={},
    )

    for idx, tool in enumerate(tool_dict.values()):
        instr.append(f"({idx + 1}) {tool}")
    instr.append(
        "When providing `next_tool_args`, the value inside the field must be in JSON format"
    )

    react_signature = (
        dspy.Signature({**signature.input_fields}, "\n".join(instr))
        .append("trajectory", dspy.InputField(), type_=str)
        .append("next_thought", dspy.OutputField(), type_=str)
        .append(
            "next_tool_name", dspy.OutputField(), type_=Literal[tuple(tool_dict.keys())]
        )
        .append("next_tool_args", dspy.OutputField(), type_=dict[str, Any])
    )
    return react_signature, tool_dict


class Planner(dspy.Module):
    def __init__(self, tools, signature=PlannerSignature, max_iterations=5):
        super().__init__()

        react_signature, tools = create_react_signature(signature, tools)

        self.tools = tools
        self.planner = dspy.Predict(react_signature)
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 3 / 15,
            "conversation_summary": 1 / 15,
            "chatbot_role": 2 / 15,
            "trajectory": 6 / 15,
        }
        self.trajectory_summary = ""
        self.max_iterations = max_iterations

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.planner, **kwargs))
        return token_limit_ratio_to_count(self.token_ratios, template_len)

    def forward(
        self,
        current_user_message: str,
        conversation_history: str,
        conversation_summary: str,
    ) -> dspy.Prediction:
        planner_inputs = dict(
            current_user_message=current_user_message,
            conversation_history=conversation_history,
            conversation_summary=conversation_summary,
            chatbot_role=role_str,
        )

        trajectory = {}
        with span_ctx_start("Planner", SpanKind.AGENT) as span:
            span.set_attribute("agent.name", "Planner")
            span.set_attribute("input.value", safe_json_dumps(planner_inputs))

            # Tool calling iterations
            for idx in range(self.max_iterations):
                planner_inputs = truncate_tokens_all(
                    planner_inputs,
                    self.get_token_limits(**planner_inputs),
                )

                try:
                    plan = self._call_with_potential_trajectory_truncation(
                        self.planner, trajectory, **planner_inputs
                    )
                except ValueError:
                    break

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
        return dspy.Prediction(
            trajectory=format_trajectory(trajectory),
            summary=self.trajectory_summary,
        )

    def _call_with_potential_trajectory_truncation(
        self, module, trajectory, **input_args
    ):
        for _ in range(3):
            try:
                return module(
                    **input_args,
                    trajectory=format_trajectory(trajectory),
                )
            except ContextWindowExceededError:
                # Trajectory exceeded the context window
                # truncating the oldest tool call information.
                new_summary, trajectory = self.truncate_trajectory(
                    trajectory, input_args["current_user_message"]
                )
                self.trajectory_summary = new_summary
        raise ValueError(
            "The context window was exceeded even after 3 attempts to truncate the trajectory."
        )

    def truncate_trajectory(self, trajectory: dict, current_user_message: str):
        """Truncates the trajectory so that it fits in the context window.

        Summarizes by using a LLM on the earliest trajectory set.
        """
        summarizer = dspy.Predict(SummarizerSignature)
        keys = list(trajectory.keys())
        if len(keys) < 4:
            # Every tool call has 4 keys: thought, tool_name, tool_args, and observation.
            raise ValueError(
                "The trajectory is too long so your prompt exceeded the context window, but the trajectory cannot be "
                "truncated because it only has one tool call."
            )

        earliest_trajectory = ""
        for key in keys[:4]:
            earliest_trajectory += str(key) + ":" + trajectory.pop(key) + "\n"
        summary = summarizer(
            current_user_message=current_user_message,
            previous_summary=self.trajectory_summary,
            trajectory_to_discard=earliest_trajectory,
        )
        return summary.new_summary, trajectory


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
