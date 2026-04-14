from typing import Any, Literal

import dspy
from dspy import Tool
from litellm.exceptions import ContextWindowExceededError
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import OpenInferenceSpanKindValues as SpanKind

from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.prompt_settings import (
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    ROLE_PROMPT,
    role_str,
)
from chatdku.core.dspy_common import get_template
from chatdku.core.utils import (
    format_trajectory,
    span_ctx_start,
    token_limit_ratio_to_count,
    truncate_tokens_all,
)


class ExecutorSignature(dspy.Signature):
    """
    You are an Executor Agent for Duke Kunshan University (DKU). You have been given a plan
    created by the Planner Agent. Your job is to execute the plan by calling the available
    tools to gather the information described in the plan.

    In each turn you can see:
        - The plan you are following.
        - Your past trajectory of tool calls and observations so far.
        - The conversation history for context.

    In each turn you produce:
        - next_thought: reason about the current state, what the plan asks for next,
          and what tool call would best fulfill it.
        - next_tool_name: the tool to call (must be one of the provided tools, or "finish").
        - next_tool_args: the arguments to pass to the tool (JSON format).

    Useful facts:
        - Available subject codes: DKU, GERMAN, INDSTU, JAPANESE, KOREAN, MUSIC, SPANISH,
            ARHU, ARTS, BEHAVSCI, BIOL, CHEM, CHINESE, COMPDSGN, COMPSCI, CULANTH, CULMOVE,
            CULSOC, EAP, ECON, ENVIR, ETHLDR, GCHINA, GCULS, GLHLTH, HIST, HUM, INFOSCI,
            INSTGOV, LIT, MATH, MATSCI, MEDIA, MEDIART, NEUROSCI, PHIL, PHYS, PHYSEDU,
            POLECON, POLSCI, PPE, PSYCH, PUBPOL, SOCIOL, SOSC, STATS, USTUD, WOC, RELIG,
            MINITERM
            People use deviations of the subject code like "CS" or "BIO" which are not official
            subject codes set by DKU. For these cases, use the subject codes above instead.

            For example:
                - "CS" OR "Computer Science" -> "COMPSCI"
                - "BIO" OR "Biology" -> "BIOL"
                - "Psychology" -> "PSYCH"
                - "Physics" -> "PHYS"
                etc.

    Call "finish" when you have gathered enough information to answer the user's question
    according to the plan, or when you determine that the information cannot be found.

    If a tool call fails, try to work around it (e.g. rephrase the query, try a different
    tool). If you fundamentally cannot fulfill part of the plan, note what failed in your
    next_thought and call finish — the Synthesizer will communicate the gap to the user.
    """

    plan: str = dspy.InputField(
        desc="The plan from the Planner describing what information to gather.",
        format=lambda x: x,
    )
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

    current_user_message: str = dspy.InputField()
    trajectory_to_discard: str = dspy.InputField(
        desc=(
            "The tool calls that would be removed from Tool History. "
            "You should extract relevant information from these tool calls."
        ),
    )
    previous_summary: str = dspy.InputField()
    new_summary: str = dspy.OutputField()


class Executor(dspy.Module):
    def __init__(self, tools, max_iterations=5):
        super().__init__()
        tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
        tools = {tool.name: tool for tool in tools}

        instr = (
            [f"{ExecutorSignature.instructions}\n"]
            if ExecutorSignature.instructions
            else []
        )

        tools["finish"] = Tool(
            func=lambda: "Completed.",
            name="finish",
            desc="Marks the task as complete. Call this when you have gathered enough information.",
            args={},
        )

        for idx, tool in enumerate(tools.values()):
            instr.append(f"({idx + 1}) {tool}")
        instr.append(
            "When providing `next_tool_args`, the value inside the field must be in JSON format"
        )

        react_signature = (
            dspy.Signature({**ExecutorSignature.input_fields}, "\n".join(instr))
            .append("trajectory", dspy.InputField(), type_=str)
            .append("next_thought", dspy.OutputField(), type_=str)
            .append(
                "next_tool_name",
                dspy.OutputField(),
                type_=Literal[tuple(tools.keys())],
            )
            .append("next_tool_args", dspy.OutputField(), type_=dict[str, Any])
        )

        self.tools = tools
        self.executor = dspy.Predict(react_signature)
        self.token_ratios: dict[str, float] = {
            "plan": 2 / 15,
            "current_user_message": 1 / 15,
            "conversation_history": 2 / 15,
            "conversation_summary": 1 / 15,
            "chatbot_role": 2 / 15,
            "trajectory": 6 / 15,
        }
        self.trajectory_summary = ""
        self.max_iterations = max_iterations

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.executor, **kwargs))
        return token_limit_ratio_to_count(self.token_ratios, template_len)

    def forward(
        self,
        plan: str,
        current_user_message: str,
        conversation_memory: ConversationMemory,
    ) -> dspy.Prediction:
        executor_inputs = dict(
            plan=plan,
            current_user_message=current_user_message,
            conversation_history=conversation_memory.history_str(),
            conversation_summary=conversation_memory.summary,
            chatbot_role=role_str,
        )

        trajectory = {}
        with span_ctx_start("Executor", SpanKind.AGENT) as span:
            span.set_attribute("agent.name", "Executor")
            span.set_attribute("input.value", safe_json_dumps(executor_inputs))

            for idx in range(self.max_iterations):
                executor_inputs = truncate_tokens_all(
                    executor_inputs,
                    self.get_token_limits(**executor_inputs),
                )

                try:
                    result = self._call_with_potential_trajectory_truncation(
                        self.executor, trajectory, **executor_inputs
                    )
                except ValueError:
                    break

                trajectory[f"thought_{idx}"] = result.next_thought
                trajectory[f"tool_name_{idx}"] = result.next_tool_name
                trajectory[f"tool_args_{idx}"] = result.next_tool_args

                try:
                    trajectory[f"observation_{idx}"] = self.tools[
                        result.next_tool_name
                    ](**result.next_tool_args)
                except Exception as err:
                    trajectory[f"observation_{idx}"] = (
                        f"Execution error in {result.next_tool_name}: {_fmt_exc(err)}"
                    )
                if result.next_tool_name == "finish":
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
