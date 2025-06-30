from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from chatdku.setup import setup, use_phoenix
        from chatdku.core.agent import CustomClient
        import core.signals
        import dspy
        setup()
        use_phoenix()

        llama_client = CustomClient()
        dspy.settings.configure(lm=llama_client)
