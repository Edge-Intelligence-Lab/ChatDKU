import dspy
from dspy.signatures.signature import ensure_signature


def get_template(predict_module: dspy.Module, **kwargs) -> str:
    """Get formatted template from predict module.
    Adapted from https://github.com/stanfordnlp/dspy/blob/55510eec1b83fa77f368e191a363c150df8c5b02/dspy/predict/llamaindex.py#L22-L36
    """
    # FIXME: This might not be an elegant way to access the predict module.
    # This is due to that `ChainOfThought` stores the predict module in `predict` attribute.
    if hasattr(predict_module, "predict"):
        predict_module = predict_module.predict

    # Extract the three privileged keyword arguments.
    signature = ensure_signature(predict_module.signature)

    inputs = kwargs
    if hasattr(predict_module, "demos"):
        demos = predict_module.demos
    else:
        demos = []

    ## template was an old dspy primitive
    ## I assume it was to get the final prompt to the llm
    ## changes made by: Temuulen
    ## Adapted from: https://github.com/stanfordnlp/dspy/issues/8259
    template = dspy.ChatAdapter().format(
        signature=signature, demos=demos, inputs=inputs
    )

    return str(template[0])


custom_cot_rationale = dspy.OutputField(
    prefix="<think>",
    desc="The step-by-step rationale of how you derive the response." + "</think>",
)
