from django.apps import AppConfig
from chatdku.config import config
import dspy
import requests


import logging
logger=logging.getLogger(__name__)
class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from chatdku.setup import setup, use_phoenix
        import dspy
        setup()
        use_phoenix()


def model_response(module,**kwargs):

    lm = dspy.LM(
    model="openai/" + config.llm,
    api_base=config.llm_url,
    api_key=config.llm_api_key,
    model_type="chat",
    max_tokens=config.context_window,
    temperature=config.llm_temperature,
    launch_kwargs={
        "TopP": 0.95,
    },
    )

    backup_lm = dspy.LM(
    model="openai/" + config.backup_llm,
    api_base=config.backup_llm_url,
    api_key=config.llm_api_key,
    model_type="chat",
    max_tokens=20000,
    temperature=config.llm_temperature,
    launch_kwargs={
        "TopP": 0.95,
    },
    )

    headers={
        "Authorization":f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json"
    }
    try:
        url=config.llm_url +'/models'
        response=requests.get(url,headers=headers,timeout=5)
        if response.ok:
            dspy.configure(lm = lm)

            dspy.configure_cache(
            enable_disk_cache=False,
            enable_memory_cache=False
            )


            return module(**kwargs)
        
        else:
            logger.warning(f"[Model Error] Primary LM unhealthy: HTTP {response.status_code}")
            with dspy.context(lm=backup_lm):
                dspy.configure_cache(
                enable_disk_cache=False,
                enable_memory_cache=False
                )
                return module(**kwargs)
    
    except Exception as e:
        logger.exception(f"[Model Error] Primary LM failed: {e}\n Switching to backup LM")


        dspy.configure(lm = backup_lm)
        return module(**kwargs)