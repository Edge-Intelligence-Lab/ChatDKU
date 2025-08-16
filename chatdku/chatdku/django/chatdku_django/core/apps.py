from django.apps import AppConfig
from chatdku.config import config
class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from chatdku.setup import setup, use_phoenix
        import dspy
        setup()
        use_phoenix()
        lm = dspy.LM(
            model="openai/" + config.llm,
            api_base=config.llm_url,
            api_key="dummy",
            model_type="chat",
            max_tokens=30000,
        )

        dspy.configure(lm=lm)
