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


class AssessSignature(dspy.Signature):
    """
    You are evaluating the progress of an information-gathering task for
    Duke Kunshan University (DKU).

    Given the plan and the tool results collected so far (trajectory), determine:
    1. What information from the plan has been successfully gathered.
    2. What information is still missing or insufficient.
    3. Whether you should continue gathering information or finish.

    Choose "continue" if the plan has unfulfilled steps that the available tools
    can still address.
    Choose "finish" if you have gathered enough information to answer the user's
    question, OR if the remaining gaps cannot be resolved with further tool calls.
    """

    plan: str = dspy.InputField(
        desc="The plan describing what information to gather.",
        format=lambda x: x,
    )
    current_user_message: str = dspy.InputField()
    trajectory: str = dspy.InputField(
        desc="Tool calls and their results collected so far. May be empty on the first iteration.",
        format=lambda x: x,
    )
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD

    assessment: str = dspy.OutputField(
        desc=(
            "Brief analysis: (1) what information has been gathered so far, "
            "(2) what is still missing from the plan, "
            "(3) whether the missing information can be obtained with available tools."
        ),
    )
    decision: str = dspy.OutputField(type=Literal["continue", "finish"])


class _ActSignatureBase(dspy.Signature):
    """
    You are an Executor Agent for Duke Kunshan University (DKU). You have been
    given a plan and an assessment of what information is still missing.
    Your job is to pick the best tool to call next to fill the identified gaps.

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

    If a previous tool call failed, try to work around it (e.g. rephrase the
    query, try a different tool).
    """

    plan: str = dspy.InputField(
        desc="The plan describing what information to gather.",
        format=lambda x: x,
    )
    current_user_message: str = dspy.InputField()
    trajectory: str = dspy.InputField(
        desc="Tool calls and their results collected so far.",
        format=lambda x: x,
    )
    assessment: str = dspy.InputField(
        desc="Analysis of what has been gathered and what is still missing.",
        format=lambda x: x,
    )
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD
    chatbot_role: str = ROLE_PROMPT


class DistillSignature(dspy.Signature):
    """
    You are given the full trajectory of tool calls made to answer a user's
    question, along with the original plan. Your job is to extract and organize
    only the information that is relevant to answering the user's question.

    Guidelines:
    - Discard executor reasoning (thoughts, assessments) and tool metadata
      (tool names, arguments). Keep only the substantive content from
      observations.
    - Preserve source attributions (document names, URLs, page numbers) so
      the Synthesizer can cite them.
    - If a tool call failed or returned irrelevant results, omit it.
    - Organize the information logically (e.g. group by topic, requirement
      category, or chronological order as appropriate).
    - Use Markdown formatting.
    """

    current_user_message: str = dspy.InputField()
    plan: str = dspy.InputField(
        desc="The plan that guided information gathering.",
        format=lambda x: x,
    )
    trajectory: str = dspy.InputField(
        desc="The full trajectory of tool calls and observations.",
        format=lambda x: x,
    )
    trajectory_summary: str = dspy.InputField(
        desc="Summary of earlier trajectory entries that were truncated. May be empty.",
        format=lambda x: x,
    )

    relevant_context: str = dspy.OutputField(
        desc=(
            "Organized extraction of information relevant to answering the "
            "user's question, with source attributions preserved."
        ),
    )


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


# Keys per iteration in the trajectory dict.
# assessment, thought, tool_name, tool_args, observation
_KEYS_PER_ITERATION = 5


class Executor(dspy.Module):
    def __init__(self, tools, max_iterations=5):
        super().__init__()
        tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
        tools = {tool.name: tool for tool in tools}

        # Build the ActSignature dynamically with tool descriptions in the instructions.
        instr = (
            [f"{_ActSignatureBase.instructions}\n"]
            if _ActSignatureBase.instructions
            else []
        )
        for idx, tool in enumerate(tools.values()):
            instr.append(f"({idx + 1}) {tool}")
        instr.append(
            "When providing `next_tool_args`, the value inside the field must be in JSON format"
        )

        act_signature = (
            dspy.Signature({**_ActSignatureBase.input_fields}, "\n".join(instr))
            .append("next_thought", dspy.OutputField(), type_=str)
            .append(
                "next_tool_name",
                dspy.OutputField(),
                type_=Literal[tuple(tools.keys())],
            )
            .append("next_tool_args", dspy.OutputField(), type_=dict[str, Any])
        )

        self.tools = tools
        self.assessor = dspy.Predict(AssessSignature)
        self.actor = dspy.Predict(act_signature)
        self.distiller = dspy.Predict(DistillSignature)

        self.assess_token_ratios: dict[str, float] = {
            "plan": 3 / 12,
            "current_user_message": 1 / 12,
            "conversation_history": 2 / 12,
            "conversation_summary": 1 / 12,
            "trajectory": 5 / 12,
        }
        self.act_token_ratios: dict[str, float] = {
            "plan": 2 / 15,
            "current_user_message": 1 / 15,
            "conversation_history": 1 / 15,
            "conversation_summary": 1 / 15,
            "chatbot_role": 2 / 15,
            "trajectory": 4 / 15,
            "assessment": 2 / 15,
        }
        self.distill_token_ratios: dict[str, float] = {
            "current_user_message": 2 / 10,
            "plan": 2 / 10,
            "trajectory": 5 / 10,
            "trajectory_summary": 1 / 10,
        }

        self.trajectory_summary = ""
        self.max_iterations = max_iterations

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        """Return token limits using the actor's ratios (tightest constraint)."""
        template_len = len(get_template(self.actor, **kwargs))
        return token_limit_ratio_to_count(self.act_token_ratios, template_len)

    def forward(
        self,
        plan: str,
        current_user_message: str,
        conversation_memory: ConversationMemory,
    ) -> dspy.Prediction:
        shared_inputs = dict(
            current_user_message=current_user_message,
            conversation_history=conversation_memory.history_str(),
            conversation_summary=conversation_memory.summary,
        )

        trajectory = {}
        with span_ctx_start("Executor", SpanKind.AGENT) as span:
            span.set_attribute("agent.name", "Executor")
            span.set_attribute(
                "input.value",
                safe_json_dumps({"plan": plan, **shared_inputs}),
            )

            for idx in range(self.max_iterations):
                formatted_traj = format_trajectory(trajectory)

                # Phase 1: ASSESS
                assess_inputs = {
                    "plan": plan,
                    **shared_inputs,
                }
                assess_inputs = truncate_tokens_all(
                    assess_inputs,
                    self._assess_token_limits(**assess_inputs),
                )

                try:
                    assess_result = self._call_with_potential_trajectory_truncation(
                        self.assessor, trajectory, **assess_inputs
                    )
                except ValueError:
                    break

                trajectory[f"assessment_{idx}"] = assess_result.assessment

                if assess_result.decision == "finish":
                    break

                # Phase 2: ACT
                act_inputs = {
                    "plan": plan,
                    **shared_inputs,
                    "assessment": assess_result.assessment,
                    "chatbot_role": role_str,
                }
                act_inputs = truncate_tokens_all(
                    act_inputs,
                    self._act_token_limits(**act_inputs),
                )

                try:
                    act_result = self._call_with_potential_trajectory_truncation(
                        self.actor, trajectory, **act_inputs
                    )
                except ValueError:
                    break

                trajectory[f"thought_{idx}"] = act_result.next_thought
                trajectory[f"tool_name_{idx}"] = act_result.next_tool_name
                trajectory[f"tool_args_{idx}"] = act_result.next_tool_args

                try:
                    trajectory[f"observation_{idx}"] = self.tools[
                        act_result.next_tool_name
                    ](**act_result.next_tool_args)
                except Exception as err:
                    trajectory[f"observation_{idx}"] = (
                        f"Execution error in {act_result.next_tool_name}: {_fmt_exc(err)}"
                    )

            # DISTILL
            formatted_traj = format_trajectory(trajectory)
            distill_inputs = dict(
                current_user_message=current_user_message,
                plan=plan,
                trajectory=formatted_traj,
                trajectory_summary=self.trajectory_summary,
            )
            distill_inputs = truncate_tokens_all(
                distill_inputs,
                self._distill_token_limits(**distill_inputs),
            )
            distill_result = self.distiller(**distill_inputs)

            span.set_attribute("output.value", safe_json_dumps(trajectory))

        return dspy.Prediction(
            relevant_context=distill_result.relevant_context,
            summary=self.trajectory_summary,
        )

    # Token limit helpers

    def _assess_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.assessor, **kwargs))
        return token_limit_ratio_to_count(self.assess_token_ratios, template_len)

    def _act_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.actor, **kwargs))
        return token_limit_ratio_to_count(self.act_token_ratios, template_len)

    def _distill_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.distiller, **kwargs))
        return token_limit_ratio_to_count(self.distill_token_ratios, template_len)

    # Trajectory management

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
        if len(keys) < _KEYS_PER_ITERATION:
            raise ValueError(
                "The trajectory is too long so your prompt exceeded the context window, but the trajectory cannot be "
                "truncated because it only has one iteration of tool calls."
            )

        earliest_trajectory = ""
        for key in keys[:_KEYS_PER_ITERATION]:
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
