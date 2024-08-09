import dsp
import dspy
from dspy.signatures.signature import ensure_signature, signature_to_template


def get_template(predict_module: dspy.Module, **kwargs) -> str:
    """Get formatted template from predict module.
    Adapted from https://github.com/stanfordnlp/dspy/blob/55510eec1b83fa77f368e191a363c150df8c5b02/dspy/predict/llamaindex.py#L22-L36
    """
    # FIXME: This might not be an elegant way to access the predict module.
    # This is due to that `ChainOfThought` stores the predict module in `_predict` attribute.
    if hasattr(predict_module, "_predict"):
        predict_module = predict_module._predict

    # Extract the three privileged keyword arguments.
    signature = ensure_signature(predict_module.signature)
    # Switch to legacy format for dsp.generate
    template = signature_to_template(signature)

    if hasattr(predict_module, "demos"):
        demos = predict_module.demos
    else:
        demos = []
    # All of the other kwargs are presumed to fit a prefix of the signature.
    # That is, they are input variables for the bottom most generation, so
    # we place them inside the input - x - together with the demos.
    x = dsp.Example(demos=demos, **kwargs)
    return template(x)


custom_cot_rationale = dspy.OutputField(
    prefix="Rationale:",
    desc="The step-by-step rationale of how you derive the response.",
)
