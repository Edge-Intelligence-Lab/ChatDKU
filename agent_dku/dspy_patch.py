"""
Custom patches to DSPy internals.
FIXME: Stop using these patches whenever the issues were addressed by DSPy.

Use Adapters as an alternative when available
See also: https://github.com/stanfordnlp/dspy/issues/409
"""

import dsp
import dspy
from dsp import passages2text, format_answers
from collections import namedtuple
import magicattr


def custom_guidelines(self, show_guidelines: bool = True) -> str:
    """Custom prompt format for the LLM to better understand the instructions."""
    if (not show_guidelines) or (
        hasattr(dsp.settings, "show_guidelines") and not dsp.settings.show_guidelines
    ):
        return ""

    input_example = dsp.Example()
    input_example.augmented = self._has_augmented_guidelines()
    output_example = dsp.Example()
    output_example.augmented = self._has_augmented_guidelines()

    for field in self.fields:
        if field.type == "input":
            input_example[field.input_variable] = field.description
        else:
            output_example[field.input_variable] = field.description

    result = "Given the input in the format below:\n\n"
    result += self.query(input_example, True)
    result += "\n\n---\n\n"
    result += (
        "Output in the format given below. "
        "Do not output anything else that does not fit into the format. "
        "Use the verbatim names of the fields in the format "
        "and do not stylize them such as **Field Name:**. "
        "Output format:\n\n"
    )
    result += self.query(output_example, True)
    return result


dsp.adapters.Template.guidelines = custom_guidelines

Field = namedtuple(
    "Field", "name separator input_variable output_variable description type"
)


def custom_init(self, instructions: str, **kwargs):
    self.instructions = instructions
    self.kwargs = kwargs

    self.fields: list[Field] = []
    self.format_handlers: dict[str, Callable] = {
        "context": passages2text,
        "passages": passages2text,
        "answers": format_answers,
    }

    for key, value in kwargs.items():
        prefix: str = value.prefix
        separator: str = (
            " "
            if prefix.rstrip() == prefix and len(prefix) > 0
            else prefix[len(prefix.rstrip()) :]
        )

        if isinstance(value, dspy.OldInputField):
            t = "input"
        elif isinstance(value, dspy.OldOutputField):
            t = "output"
        else:
            t = value.json_schema_extra["__dspy_field_type"]

        field = Field(
            name=prefix.strip(),
            description=value.desc,
            input_variable=key,
            output_variable=key,
            separator=separator,
            type=t,
        )
        self.fields.append(field)

        if value.format:
            self.format_handlers[key] = value.format


dsp.adapters.BaseTemplate.__init__ = custom_init


def custom_call(self, example, show_guidelines=True) -> str:
    example = dsp.Example(example)

    if hasattr(dsp.settings, "query_only") and dsp.settings.query_only:
        return self.query(example)

    # The training data should not contain the output variable
    if self.fields[-1].input_variable in example:
        del example[self.fields[-1].input_variable]

    rdemos = [
        self.query(demo, is_demo=True)
        for demo in example.demos
        if (
            (not demo.get("augmented", False))
            and (  # validate that the training example has the same primitive input var as the template
                self.fields[-1].input_variable in demo
                and demo[self.fields[-1].input_variable] is not None
            )
        )
    ]

    ademos = [
        self.query(demo, is_demo=True)
        for demo in example.demos
        if demo.get("augmented", False)
    ]

    # Move the rdemos to ademos if rdemo has all the fields filled in
    rdemos_ = []
    new_ademos = []
    for rdemo in rdemos:
        if all(
            (field.name in rdemo)
            for field in self.fields
            if field.input_variable in example
        ):
            import dspy

            if dspy.settings.release >= 20230928:
                new_ademos.append(rdemo)
            else:
                ademos.append(rdemo)
        else:
            rdemos_.append(rdemo)

    ademos = new_ademos + ademos
    rdemos = rdemos_

    long_query = self._has_augmented_guidelines()

    if long_query:
        example["augmented"] = True

    query = self.query(example)

    # Always do `long_query`
    if not example.get("augmented", False):
        example["augmented"] = True
        query = self.query(example)

    rdemos = "\n\n".join(rdemos)

    if len(rdemos) == 0:
        parts = [
            self.instructions,
            self.guidelines(show_guidelines),
            *ademos,
            query,
        ]
    else:
        parts = [
            self.instructions,
            rdemos,
            self.guidelines(show_guidelines),
            *ademos,
            query,
        ]

    prompt = "<|start_header_id|>system<|end_header_id|>\n\n"
    prompt += "\n\n---\n\n".join([p.strip() for p in parts[:-1] if p])
    prompt += "<|eot_id|>\n"
    prompt += "<|start_header_id|>user<|end_header_id|>\n\n"
    prompt += parts[-1].strip()
    prompt += "<|eot_id|>\n"
    prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

    return prompt.strip()


dsp.adapters.Template.__call__ = custom_call


def custom_set_attribute_by_name(obj, name, value):
    magicattr.set(obj, name, value)


dspy.primitives.program.set_attribute_by_name = custom_set_attribute_by_name
