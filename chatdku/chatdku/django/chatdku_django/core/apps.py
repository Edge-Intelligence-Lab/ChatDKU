from django.apps import AppConfig
from chatdku.config import config
import dspy
import threading




import logging
logger=logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    def ready(self):
        from chatdku.setup import setup, use_phoenix
        setup()
        use_phoenix()
        lm = dspy.LM(
        model="openai/" + config.llm,
        api_base=config.llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.context_window,
        temperature=config.llm_temperature,
        )
        dspy.configure(lm=lm)
        
        dspy.configure_cache(
        enable_disk_cache=True,
        enable_memory_cache=True
        )
