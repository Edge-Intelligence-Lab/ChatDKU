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
