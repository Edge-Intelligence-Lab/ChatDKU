import logging
import os

# Must be set before `import dspy` — prevents litellm from fetching the remote
# model pricing database at startup (cuts ~40s off cold-start time).
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")  # noqa: E402,E401

import dspy
from django.apps import AppConfig

from chatdku.config import config

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        from chatdku.setup import setup, use_phoenix

        setup()
        use_phoenix()
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

        dspy.configure_cache(enable_disk_cache=True, enable_memory_cache=True)
