"""
Integration test: verify that litellm raises ContextWindowExceededError
when the input is far larger than the model's context window.
"""

import dspy
import pytest
from litellm import ContextWindowExceededError

from chatdku.config import config


class HugeInputSignature(dspy.Signature):
    """Answer the question."""

    question: str = dspy.InputField()
    answer: str = dspy.OutputField()


def test_context_window_exceeded():
    lm = dspy.LM(
        model="openai/" + config.backup_llm,
        api_base=config.backup_llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.context_window,
        temperature=config.llm_temperature,
    )
    dspy.configure(lm=lm)

    predictor = dspy.Predict(HugeInputSignature)

    # Build a string way larger than the 32k context window
    huge_input = "hello world " * 500_000  # ~6M tokens

    with pytest.raises(ContextWindowExceededError):
        predictor(question=huge_input)
