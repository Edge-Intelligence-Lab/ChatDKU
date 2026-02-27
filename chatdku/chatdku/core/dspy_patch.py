"""
Custom patches to DSPy internals.
FIXME: Stop using these patches whenever the issues were addressed by DSPy.

`custom_guidelines` and `custom_call` are for implementing the custom prompt format.
`custom_call` is basically for differentiating between input and output fields.
Should use Adapters as an alternative when available
See also: https://github.com/stanfordnlp/dspy/issues/409
"""

import dsp
import dspy
from dsp import passages2text, format_answers
from collections import namedtuple
import magicattr
from dspy.primitives.assertions import (
    DSPyAssertionError,
    DSPySuggestionError,
    _build_error_msg,
    bypass_suggest_handler,
)


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
    """Patch for supporting assertion for complex modules.
    See: https://github.com/stanfordnlp/dspy/pull/1301
    """
    magicattr.set(obj, name, value)


dspy.primitives.program.set_attribute_by_name = custom_set_attribute_by_name


def custom_backtrack_handler(func, bypass_suggest=True, max_backtracks=2):
    """Workaround for https://github.com/stanfordnlp/dspy/issues/1356
    Might cause some unforeseen issues as one test failed in the PR.
    """

    def wrapper(*args, **kwargs):
        error_msg, result = None, None
        with dspy.settings.lock:
            dspy.settings.backtrack_to = None
            dspy.settings.suggest_failures = 0
            dspy.settings.assert_failures = 0

            # Predictor -> List[feedback_msg]
            dspy.settings.predictor_feedbacks = {}

            current_error = None
            for i in range(max_backtracks + 1):
                if i > 0 and dspy.settings.backtrack_to is not None:
                    # generate values for new fields
                    feedback_msg = _build_error_msg(
                        dspy.settings.predictor_feedbacks[dspy.settings.backtrack_to],
                    )

                    dspy.settings.backtrack_to_args = {
                        "feedback": feedback_msg,
                        "past_outputs": past_outputs,
                    }

                # if last backtrack: ignore suggestion errors
                if i == max_backtracks:
                    if isinstance(current_error, DSPyAssertionError):
                        raise current_error
                    dsp.settings.trace.clear()
                    result = (
                        bypass_suggest_handler(func)(*args, **kwargs)
                        if bypass_suggest
                        else None
                    )
                    break
                else:
                    try:
                        dsp.settings.trace.clear()
                        result = func(*args, **kwargs)
                        break
                    except (DSPySuggestionError, DSPyAssertionError) as e:
                        if not current_error:
                            current_error = e
                        error_id, error_msg, error_target_module, error_state = (
                            e.id,
                            e.msg,
                            e.target_module,
                            e.state[-1],
                        )

                        # increment failure count depending on type of error
                        if isinstance(e, DSPySuggestionError) and e.is_metric:
                            dspy.settings.suggest_failures += 1
                        elif isinstance(e, DSPyAssertionError) and e.is_metric:
                            dspy.settings.assert_failures += 1

                        if dsp.settings.trace:
                            if error_target_module:
                                for i in range(len(dsp.settings.trace) - 1, -1, -1):
                                    trace_element = dsp.settings.trace[i]
                                    mod = trace_element[0]
                                    if mod.signature == error_target_module:
                                        error_state = e.state[i]
                                        dspy.settings.backtrack_to = mod
                                        break
                            else:
                                dspy.settings.backtrack_to = dsp.settings.trace[-1][0]

                            if dspy.settings.backtrack_to is None:
                                dspy.logger.error("Specified module not found in trace")

                            # save unique feedback message for predictor
                            if (
                                error_msg
                                not in dspy.settings.predictor_feedbacks.setdefault(
                                    dspy.settings.backtrack_to,
                                    [],
                                )
                            ):
                                dspy.settings.predictor_feedbacks[
                                    dspy.settings.backtrack_to
                                ].append(error_msg)

                            output_fields = error_state[0].new_signature.output_fields
                            past_outputs = {}
                            for field_name in output_fields.keys():
                                past_outputs[field_name] = getattr(
                                    error_state[2],
                                    field_name,
                                    None,
                                )

                            # save latest failure trace for predictor per suggestion
                            error_ip = error_state[1]
                            error_op = error_state[2].__dict__["_store"]
                            error_op.pop("_assert_feedback", None)
                            error_op.pop("_assert_traces", None)

                        else:
                            dspy.logger.error(
                                "UNREACHABLE: No trace available, this should not happen. Is this run time?",
                            )

            return result

    return wrapper


dspy.primitives.assertions.backtrack_handler = custom_backtrack_handler
