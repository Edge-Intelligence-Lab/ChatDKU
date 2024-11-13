from typing import Literal
from pydantic import ConfigDict, Field, create_model, ValidationError
from pydantic.fields import FieldInfo

import dspy

from contextlib import nullcontext
from openinference.instrumentation import safe_json_dumps
from opentelemetry.trace import Status, StatusCode
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)

from chatdku.agent_dku.dspy_common import get_template, custom_cot_rationale
from chatdku.agent_dku.utils import (
    NameParams,
    func_to_model,
    camel_to_snake_case,
    truncate_tokens_all,
    token_limit_ratio_to_count,
)
from chatdku.agent_dku.dspy_classes.conversation_memory import ConversationMemory
from chatdku.agent_dku.dspy_classes.tool_memory import ToolMemory
from chatdku.agent_dku.dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
    ROLE_PROMPT,
)

from chatdku.config import config


def make_planner_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "conversation_history": (str, CONVERSATION_HISTORY_FIELD),
        "conversation_summary": (str, CONVERSATION_SUMMARY_FIELD),
        "available_tools": (
            str,
            dspy.InputField(
                desc=(
                    "A list of available tools and their respective parameters. "
                    "The JSON schema for each tool is presented on a single line, "
                    "including the tool's name, description, and a list of "
                    "its parameters with descriptions for each parameter."
                ),
                # Preserve linebreaks in the format.
                # However, it won't work if you implement the actual formatting function here,
                # as the input would be convert to string first.
                format=lambda x: x,
            ),
        ),
        "max_calls": (
            str,
            dspy.InputField(
                desc="The maximum number of tool calls you can include in your plan."
            ),
        ),
        "tool_history": (str, TOOL_HISTORY_FIELD),
        "tool_summary": (str, TOOL_SUMMARY_FIELD),
        "previous_tool_plan": (
            str,
            dspy.InputField(
                desc=(
                    "Your previous plan about what tools to call next in JSON Lines format. "
                    "Each line specifies the name and parameters of the tools to be called next. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "current_tool_plan": (
            str,
            dspy.OutputField(
                # FIXME: Currently giving an example to reduce error. We might not need
                # and example after using DSPy for automatic prompting.
                desc=(
                    "Your step-by-step plan of the tools to call and their respective "
                    "parameters in JSON Lines format. "
                    "Each tool call should be a JSON object printed on a singled line. "
                    "Each tool call should be on its own line. "
                    "Strictly follow the output format specification. "
                    "Do not output in a numbered list. "
                    "Do not add explanations.\n"
                    "For example, the following two lines are an example of two valid tool calls:\n"
                    '{"name": "keyword_retriever", "params": {"query": "keyword another-keyword"}}\n'
                    '{"name": "vector_retriever", "params": {"query": "a query"}}'
                ),
                format=lambda x: x,
            ),
        ),
    }

    instruction = (
        "Your current task is to answer the Current User Message using the tools given below. "
        "Please generate a step-by-step plan of the tools you want to use and their respective parameters. "
        "All tool parameters are required."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "PlannerSignature"
    )


PlannerSignature = make_planner_signature()


class Planner(dspy.Module):
    def __init__(self, tools: list[dspy.Module]):
        super().__init__()

        self.tools = tools

        self.name_to_model = {}
        for tool in tools:
            tool_name_camel = type(tool).__name__
            tool_description = type(tool).__doc__ or ""

            tool_name_snake = camel_to_snake_case(tool_name_camel)

            Params = func_to_model(
                tool_name_camel + "Params", tool.forward, exclude=["internal_memory"]
            )
            ToolModel = create_model(
                tool_name_camel,
                model_config=ConfigDict(extra="forbid"),
                name=(
                    Literal[tool_name_snake],
                    Field(..., description=tool_description),
                ),
                params=(Params, FieldInfo()),
                __base__=NameParams,
            )
            self.name_to_model[tool_name_snake] = ToolModel

        self.planner = dspy.ChainOfThought(
            PlannerSignature, rationale_type=custom_cot_rationale
        )

        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 2 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
            "previous_tool_plan": 1 / 15,
        }

    def get_token_limits(self) -> dict[str, int]:
        template_len = len(
            get_template(
                self.planner,
                available_tools="\n".join(
                    [str(m.model_json_schema()) for m in self.name_to_model.values()]
                ),
                max_calls=str(1),
            )
        )
        return token_limit_ratio_to_count(self.token_ratios, template_len)

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
        max_calls: int = 5,
    ):
        """
        Generate a plan of tool calls and return the first tool and respective parameters.
        """
        with (
            config.tracer.start_as_current_span("Planner")
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.CHAIN.value,
            )

            planner_inputs = dict(
                current_user_message=current_user_message,
                conversation_history="\n".join(
                    [i.model_dump_json() for i in conversation_memory.history]
                ),
                conversation_summary=conversation_memory.summary,
                tool_history="\n".join(
                    [i.model_dump_json() for i in tool_memory.history]
                ),
                tool_summary=tool_memory.summary,
                previous_tool_plan="\n".join(
                    [i.model_dump_json() for i in tool_memory.plan]
                ),
            )
            planner_inputs = truncate_tokens_all(
                planner_inputs, self.get_token_limits()
            )
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(planner_inputs),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            plan_str_all = self.planner(
                available_tools="\n".join(
                    [str(m.model_json_schema()) for m in self.name_to_model.values()]
                ),
                max_calls=str(max_calls),
                **planner_inputs,
            ).current_tool_plan

            # Parse tool plan response

            plan_strs = plan_str_all.strip().split("\n")
            plan_strs = [s.strip() for s in plan_strs]
            dspy.Assert(len(plan_strs) >= 1, "Must use at least one tool.")
            dspy.Assert(
                len(plan_strs) <= max_calls,
                f"The number of tool calls in your plan must be no more than {max_calls}.",
            )

            calls_unvalidated = []
            for i, s in enumerate(plan_strs, 1):
                try:
                    calls_unvalidated.append(NameParams.model_validate_json(s))
                except ValidationError as e:
                    dspy.Assert(False, f"ValidationError on tool call line {i}: {e}")

            calls = []
            for i, c in enumerate(calls_unvalidated, 1):
                dspy.Assert(
                    c.name in self.name_to_model,
                    (
                        f'"{c.name}" is not a valid tool. '
                        f'Available tool(s) are: {", ".join(self.name_to_model)}.'
                    ),
                )
                try:
                    calls.append(
                        self.name_to_model[c.name](name=c.name, params=c.params)
                    )
                except ValidationError as e:
                    dspy.Assert(False, f"ValidationError on tool call line {i}: {e}")
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(calls),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            # FIXME: These should be put into class attributes if possible.
            # However, a DSPy bug made this impossible for now.
            # The bug causes dspy.Module.named_parameters() to enter infinite recursion
            # when duplicate references to a Module B occur in a Module A.
            name_to_tool = {}
            for tool in self.tools:
                tool_name_camel = type(tool).__name__
                tool_name_snake = camel_to_snake_case(tool_name_camel)
                name_to_tool[tool_name_snake] = tool

            span.set_status(Status(StatusCode.OK))
            return dspy.Prediction(
                calls=calls,
                tool=name_to_tool[calls[0].name],
            )
