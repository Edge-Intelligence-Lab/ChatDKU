#!/usr/bin/env python3
import re

from typing import Any, Callable, Literal
from pydantic import  ConfigDict, BaseModel, Field, create_model, ValidationError
from inspect import signature, Signature
from pydantic.fields import FieldInfo

import dspy
from dspy.primitives.assertions import assert_transform_module, backtrack_handler
from dspy.signatures.signature import ensure_signature, signature_to_template


from dspy_common import custom_cot_rationale
from dspy_classes.prompt_settings import CURRENT_USER_MESSAGE_FIELD, ROLE_PROMPT
from dspy_classes.tool_memory import ToolMemory

class NameParamsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    params: dict[str, Any]


def func_to_model(
    name: str, func: Callable[..., Any], exclude: list[str] = []
) -> type[BaseModel]:
    fields = {}
    params = signature(func).parameters

    for param_name in params:
        if param_name in exclude:
            continue

        param_type = params[param_name].annotation
        if param_type is Signature.empty:
            param_type = Any

        param_default = params[param_name].default
        if param_default is Signature.empty:
            fields[param_name] = (param_type, Field(...))
        elif isinstance(param_default, FieldInfo):
            fields[param_name] = (param_type, param_default)
        else:
            fields[param_name] = (param_type, Field(default=param_default))

    return create_model(name, **fields)


def camel_to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()

def make_planner_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
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
        "tools_called": (
            str,
            dspy.InputField(
                desc=(
                    "A list of your previous tool calls, each line specifying a tool call. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "tool_memory": (
            str,
            dspy.InputField(
                desc=(
                    "Memory of what you have learned previously from the tools. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "previous_tool_plan": (
            str,
            dspy.InputField(
                desc=(
                    "Your previous plan about what tools to call next. "
                    "Note that you have not called these tools yet. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "current_tool_plan": (
            str,
            dspy.OutputField(
                desc=(
                    "Your step-by-step plan of the tools to call and their respective "
                    "parameters in JSON Lines format. "
                    "Each tool call should be a JSON object printed on a singled line. "
                    "Each tool call should be on its own line. "
                ),
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

            Params = func_to_model(tool_name_camel + "Params", tool.forward)
            NameParams = create_model(
                tool_name_camel,
                model_config=ConfigDict(extra="forbid"),
                name=(
                    Literal[tool_name_snake],
                    Field(..., description=tool_description),
                ),
                params=(Params, FieldInfo()),
            )
            self.name_to_model[tool_name_snake] = NameParams

        self.planner = dspy.ChainOfThought(
            PlannerSignature, rationale_type=custom_cot_rationale
        )

    def forward(
        self, current_user_message: str, tool_memory: ToolMemory, max_calls: int = 5
    ):
        """
        Generate a plan of tool calls and return the first tool and respective parameters.
        """

        plan_str_all = self.planner(
            current_user_message=current_user_message,
            available_tools="\n".join(
                [str(m.model_json_schema()) for m in self.name_to_model.values()]
            ),
            max_calls=str(max_calls),
            tools_called="\n".join(
                [tool.model_dump_json() for tool in tool_memory.tools_called]
            ),
            tool_memory=tool_memory.memory,
            previous_tool_plan="\n".join(
                [tool.model_dump_json() for tool in tool_memory.tool_plan]
            ),
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
                calls_unvalidated.append(NameParamsModel.model_validate_json(s))
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
                calls.append(self.name_to_model[c.name](name=c.name, params=c.params))
            except ValidationError as e:
                dspy.Assert(False, f"ValidationError on tool call line {i}: {e}")

        # FIXME: These should be put into class attributes if possible.
        # However, a DSPy bug made this impossible for now.
        # The bug causes dspy.Module.named_parameters() to enter infinite recursion
        # when duplicate references to a Module B occur in a Module A.
        name_to_tool = {}
        for tool in self.tools:
            tool_name_camel = type(tool).__name__
            tool_name_snake = camel_to_snake_case(tool_name_camel)
            name_to_tool[tool_name_snake] = tool

        return dspy.Prediction(
            calls=calls,
            tool=name_to_tool[calls[0].name],
            schema=self.name_to_model[calls[0].name].model_json_schema(),
        )
