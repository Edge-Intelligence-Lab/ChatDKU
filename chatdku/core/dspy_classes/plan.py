from typing import Literal

import dspy
from dspy import Tool
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
    span_ctx_start,
    token_limit_ratio_to_count,
    truncate_tokens_all,
)


class PlannerSignature(dspy.Signature):
    """
    You are a Planner Agent for Duke Kunshan University (DKU). You are given the user's
    current message and the conversation history. Your job is to decide what to do next:

    1. If you can answer the user directly from the conversation history or general knowledge
       (e.g. a follow-up question, clarification, or casual conversation), choose action_type
       "send_message" and write your response in action.

    2. If information is missing and you need to ask the user a question before you can
       proceed (e.g. their major, year, or completed courses for a schedule request),
       choose action_type "send_message" and write the follow-up question in action.

    3. If the user's question requires looking up information using the available tools,
       choose action_type "plan" and write a free-form plan in action describing what
       information needs to be gathered and why. The plan will be handed to an Executor
       who has access to the same tools and will decide which specific tools to call.

    You are given descriptions of the available tools so you know what actions are possible.
    Write plans at a high level — describe *what* information is needed, not the exact
    tool calls. The Executor will figure out the specifics.

    Side notes:
        - If the user uses abbreviations or acronyms, you plan's first step should be to
          look up the full name of the abbreviation or acronym.

    Schedule and course-planning questions:
        When the user asks for a next-semester schedule, course plan, or "what courses should
        I take", you MUST verify ALL of the following are known before choosing action_type
        "plan":
            1. The student's major (and track, if applicable).
            2. Their year of matriculation (Class of 20XX).
            3. Courses they have already completed OR are currently taking.
        If any of these are missing from the current message and the conversation history,
        choose action_type "send_message" and ask for the missing information.

        Once you have all three pieces of information, your plan should:
            a. FIRST retrieve year-specific academic policies for the student's
               class year — e.g. query "Year 1 fall semester mandatory courses",
               "freshman requirements DKU 101 writing", or
               "Class of 20XX graduation requirements". Use VectorRetriever or
               KeywordRetriever. The Executor will extend its agenda based on any
               mandatory courses or policy constraints it discovers.
            b. Call CourseRecommender with the student's major and completed_courses
               to get the baseline eligibility and schedule availability report.
               This single tool handles requirements lookup, schedule availability,
               and prerequisite checking in one step — prefer it over calling
               MajorRequirementsLookup, CourseScheduleLookup, and PrerequisiteLookup
               individually.
            c. Optionally supplement with VectorRetriever or QueryCurriculum if the
               student asks for more detail on specific courses (syllabus, instructor,
               course description, etc.).
    """

    current_user_message: str = dspy.InputField()
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    chatbot_role: str = ROLE_PROMPT
    available_tools: str = dspy.InputField(
        desc="Descriptions of the tools available to the Executor.",
        format=lambda x: x,
    )
    action_type: str = dspy.OutputField(type=Literal["plan", "send_message"])
    action: str = dspy.OutputField(
        desc=(
            'If action_type is "plan": a free-form plan describing what information '
            "to gather and why. "
            'If action_type is "send_message": the message to send to the user.'
        ),
    )


PLANNER_DEMOS = [
    dspy.Example(
        current_user_message="What is CR/NC policy?",
        action_type="plan",
        action=(
            "The user is asking about DKU's Credit/No Credit (CR/NC) grading policy. "
            "This is a university policy question that requires searching DKU's documents. "
            "Search for information about the CR/NC policy, including eligibility, deadlines, "
            "and how it affects GPA."
        ),
    ).with_inputs("current_user_message"),
    dspy.Example(
        current_user_message=("what are the major requirements for X major"),
        action_type="plan",
        action=(
            "The user wants the full list of requirements for the X major, "
            "Y track. Look up the major-specific requirements for this "
            "major and track combination. Also retrieve the university-wide common-core "
            "requirements that apply to all majors."
        ),
    ).with_inputs("current_user_message"),
    dspy.Example(
        current_user_message="where is jia yan's office?",
        action_type="plan",
        action=(
            "The user is looking for the office location of a person named Jia Yan, "
            "likely a faculty or staff member at DKU. Search for information about "
            "Jia Yan including their office location, building, and room number."
        ),
    ).with_inputs("current_user_message"),
    dspy.Example(
        current_user_message="a+，a，a-什么的呢？你这个不全呀",
        action_type="plan",
        action=(
            "The user is asking about the full grading scale at DKU (A+, A, A-, etc.), "
            "and seems unsatisfied with a previous incomplete answer. Search for the "
            "complete DKU grading scale including all letter grades, their GPA point "
            "values, and any related grading policies."
        ),
    ).with_inputs("current_user_message"),
    dspy.Example(
        current_user_message="What is the scoring standard for NSPHST and graduation requirement?",
        action_type="plan",
        action=(
            "The user is asking about the scoring standard for NSPHST and graduation requirement. "
            "'NSPHST' might be an abbreviation. I need to first look up the full name of the abbreviation. "
            "Then, I can search for the relevant information including the scoring standard and graduation requirement."
        ),
    ).with_inputs("current_user_message"),
    dspy.Example(
        current_user_message="what courses should I take next semester?",
        action_type="send_message",
        action=(
            "I'd be happy to help you plan your courses for next semester! "
            "To give you a good recommendation, I'll need a few details:\n"
            "1. What is your major (and track, if applicable)?\n"
            "2. What is your year of matriculation (e.g. Class of 2027)?\n"
            "3. What courses have you already completed or are currently taking?"
        ),
    ).with_inputs("current_user_message"),
    dspy.Example(
        current_user_message=(
            "I'm a Data Science major, Class of 2027. "
            "I've completed MATH 105, STATS 201, COMPSCI 101, and ECON 101. "
            "What courses should I take next semester?"
        ),
        action_type="plan",
        action=(
            "The student has provided all required information: major (Data Science), "
            "year (Class of 2027), completed courses (MATH 105, STATS 201, COMPSCI 101, ECON 101). "
            "Class of 2027 means they matriculated in Fall 2023, so they are currently in Year 2 "
            "(assuming Fall 2026 is next semester) or Year 3 depending on current date. "
            "Step 1: Retrieve year-specific academic policies — search for 'Year 2 requirements' "
            "or 'sophomore mandatory courses DKU' to identify any mandatory courses the student "
            "must take based on their class year (e.g. DKU 101, writing requirement for Year 1; "
            "GCHINA 101 for Year 1 Spring; GLOCHALL 201 for Year 2). "
            "Step 2: Call CourseRecommender with major='data science' and "
            "completed_courses=['MATH 105', 'STATS 201', 'COMPSCI 101', 'ECON 101'] to get the "
            "baseline eligibility and schedule availability report. "
            "The Executor should extend its agenda if the policy search reveals mandatory courses "
            "not yet covered by CourseRecommender."
        ),
    ).with_inputs("current_user_message"),
]


class Planner(dspy.Module):
    def __init__(self, tools):
        super().__init__()
        tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]

        tool_descriptions = []
        for idx, tool in enumerate(tools):
            tool_descriptions.append(f"({idx + 1}) {tool}")

        self.tool_descriptions_str = "\n".join(tool_descriptions)
        self.planner = dspy.ChainOfThought(PlannerSignature)
        self.planner.demos = PLANNER_DEMOS
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 12,
            "conversation_history": 3 / 12,
            "conversation_summary": 1 / 12,
            "chatbot_role": 2 / 12,
            "available_tools": 2 / 12,
        }

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        template_len = len(get_template(self.planner, **kwargs))
        return token_limit_ratio_to_count(self.token_ratios, template_len)

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
    ) -> dspy.Prediction:
        planner_inputs = dict(
            current_user_message=current_user_message,
            conversation_history=conversation_memory.history_str(),
            conversation_summary=conversation_memory.summary,
            chatbot_role=role_str,
            available_tools=self.tool_descriptions_str,
        )

        with span_ctx_start("Planner", SpanKind.AGENT) as span:
            span.set_attribute("agent.name", "Planner")
            span.set_attribute("input.value", safe_json_dumps(planner_inputs))

            planner_inputs = truncate_tokens_all(
                planner_inputs,
                self.get_token_limits(**planner_inputs),
            )

            result = self.planner(**planner_inputs)

            span.set_attribute(
                "output.value",
                safe_json_dumps(
                    {"action_type": result.action_type, "action": result.action}
                ),
            )

        return dspy.Prediction(
            action_type=result.action_type,
            action=result.action,
        )
