from datetime import date
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


class ExecutorSignatureBase(dspy.Signature):
    """You are an Executor Agent for Duke Kunshan University (DKU) gathering
    information to answer a user's question.

    Given the plan and the tool results collected so far (trajectory), do the following in order:

    1. Assess progress:
       1. What information from the plan has been successfully gathered.
       2. What information is still missing or insufficient.
       3. What NEW investigation areas have been REVEALED by the tool results so far
       that were not in the original agenda — for example, a retrieved policy document
       mentions a mandatory course, or schedule data reveals an unmet prerequisite chain.

    You MUST pursue the full current agenda — including any extensions discovered
    during earlier steps — not just the original plan. If the assessment reveals
    new requirements (e.g., a policy document names a mandatory course), investigate
    those before finishing.

    2. Decide whether to continue or finish:
       - Choose "finish" in the next_tool_name field if you have gathered enough
         information to answer the user's question, OR if the remaining gaps cannot
         be resolved with further tool calls.

    3. If continuing, pick the best tool to call next to fill the identified
       gaps. If a previous tool call failed, try to work around it (e.g.
       rephrase the query, try a different tool).

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
    """

    current_agenda: str = dspy.InputField(
        desc=(
            "The current investigation agenda: the original plan plus any extensions "
            "discovered during execution. This is the full set of things to pursue."
        ),
        format=lambda x: x,
    )
    current_user_message: str = dspy.InputField()
    trajectory: str = dspy.InputField(
        desc="Tool calls and their results collected so far. May be empty on the first iteration.",
        format=lambda x: x,
    )
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    chatbot_role: str = ROLE_PROMPT
    current_date: date = dspy.InputField()
    assessment: str = dspy.OutputField(
        desc=(
            "Brief analysis: (1) what information has been gathered so far, "
            "(2) what is still missing from the plan, "
            "(3) whether the missing information can be obtained with available tools."
        ),
        format=lambda x: x,
    )
    agenda_extensions: str = dspy.OutputField(
        desc=(
            "New investigation areas revealed by the tool results that are NOT yet "
            "in the current agenda. Describe each as a short action phrase. "
            "Leave empty if nothing new was discovered."
        ),
    )

    assessment: str = dspy.OutputField(
        desc=(
            "Brief analysis: (1) what information has been gathered so far, "
            "(2) what is still missing from the plan, "
            "(3) whether the missing information can be obtained with available tools."
        ),
    )


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
# tool_name, tool_args, observation
_KEYS_PER_ITERATION = 4


class Executor(dspy.Module):
    def __init__(self, tools, max_iterations=5):
        super().__init__()
        tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
        tools = {tool.name: tool for tool in tools}

        # Build the Executor signature dynamically with tool descriptions in the instructions.
        instr = (
            [f"{ExecutorSignatureBase.instructions}\n"]
            if ExecutorSignatureBase.instructions
            else []
        )
        outputs = ", ".join(
            [f"`{k}`" for k in ExecutorSignatureBase.output_fields.keys()]
        )

        tools["finish"] = Tool(
            func=lambda: "Completed.",
            name="finish",
            desc=f"Marks the task as complete. That is, signals that all information for producing the outputs, i.e. {outputs}, are now available to be extracted.",
            args={},
        )

        for idx, tool in enumerate(tools.values()):
            instr.append(f"({idx + 1}) {tool}")
        instr.append(
            "When providing `next_tool_args`, the value inside the field must be in JSON format. "
        )

        exec_signature = (
            dspy.Signature(
                {
                    **ExecutorSignatureBase.input_fields,
                    **ExecutorSignatureBase.output_fields,
                },
                "\n".join(instr),
            )
            .append("next_thought", dspy.OutputField(), type_=str)
            .append(
                "next_tool_name",
                dspy.OutputField(),
                type_=Literal[tuple(tools.keys())],
            )
            .append("next_tool_args", dspy.OutputField(), type_=dict[str, Any])
        )

        self.tools = tools
        self.executor = dspy.Predict(exec_signature)
        self.distiller = dspy.Predict(DistillSignature)

        self.distill_token_ratios: dict[str, float] = {
            "current_user_message": 2 / 10,
            "plan": 2 / 10,
            "trajectory": 5 / 10,
            "trajectory_summary": 1 / 10,
        }

        self.trajectory_summary = ""
        self.max_iterations = max_iterations

    def forward(
        self,
        plan: str,
        current_user_message: str,
        conversation_memory: ConversationMemory,
    ) -> dspy.Prediction:
        # current_agenda starts as the original plan and grows as the Executor
        # discovers new investigation areas from tool results.
        current_agenda = plan

        trajectory = {}
        with span_ctx_start("Executor", SpanKind.AGENT) as span:
            for idx in range(self.max_iterations):
                executor_inputs = dict(
                    current_agenda= current_agenda,
                    current_user_message=current_user_message,
                    conversation_history=conversation_memory.history_str(),
                    conversation_summary=conversation_memory.summary,
                    current_date=str(date.today()),
                    chatbot_role= role_str,
                )

                span.set_attribute("agent.name", "Executor")
                span.set_attribute(
                    "input.value",
                    safe_json_dumps(executor_inputs)
                )

                try:
                    executor_result = self._call_with_potential_trajectory_truncation(
                        self.executor, trajectory, **executor_inputs
                    )
                except ValueError:
                    break

                if executor_result.next_tool_name == "finish":
                    break

                # NOTE: By Temuulen - I don't think we need to record assessment
                # The agent can just assess everyturn and the assessment can act like
                # a thought process guideline
                extensions = getattr(executor_result, "agenda_extensions", "").strip()
                if extensions:
                    current_agenda = (
                        f"{current_agenda}\n\n"
                        f"[Additional areas to investigate, discovered at step {idx + 1}]:\n"
                        f"{extensions}"
                    )
                trajectory[f"thought_{idx}"] = executor_result.next_thought
                trajectory[f"tool_name_{idx}"] = executor_result.next_tool_name
                trajectory[f"tool_args_{idx}"] = executor_result.next_tool_args

                try:
                    trajectory[f"observation_{idx}"] = self.tools[
                        executor_result.next_tool_name
                    ](**executor_result.next_tool_args)
                except Exception as err:
                    trajectory[f"observation_{idx}"] = (
                        f"Execution error in {executor_result.next_tool_name}: {_fmt_exc(err)}"
                    )

            # DISTILL — pass the final (extended) agenda so the distiller knows
            # everything that was investigated, including any on-the-fly extensions.
            formatted_traj = format_trajectory(trajectory)
            distill_inputs = dict(
                current_user_message=current_user_message,
                plan=current_agenda,
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
