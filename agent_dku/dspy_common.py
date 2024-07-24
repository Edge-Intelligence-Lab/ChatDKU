import dspy

custom_cot_rationale = dspy.OutputField(
    prefix="Rationale:",
    desc="The step-by-step rationale of how you derive the response.",
)
