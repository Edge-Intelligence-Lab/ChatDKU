"""
Integration test: verify that litellm raises ContextWindowExceededError
when the input is far larger than the model's context window.
"""

import dspy
import pytest
from litellm.exceptions import ContextWindowExceededError

from chatdku.config import config


class HugeInputSignature(dspy.Signature):
    """Answer the question."""

    question: str = dspy.InputField()
    answer: str = dspy.OutputField()


def test_context_window_exceeded():
    lm = dspy.LM(
        model="openai/" + config.llm,
        api_base=config.llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.output_window,
        top_p=config.top_p,
        min_p=config.min_p,
        presence_penalty=config.presence_penalty,
        repetition_penalty=config.repetition_penalty,
        temperature=config.llm_temperature,
        extra_body={
            "top_k": config.top_k,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        enable_thinking=False,
    )
    dspy.configure(lm=lm)

    predictor = dspy.Predict(HugeInputSignature)

    # Build a string way larger than the 32k context window
    huge_input = "hello world " * 500_000  # ~6M tokens

    with pytest.raises(ContextWindowExceededError):
        predictor(question=huge_input).answer
