from fastapi import FastAPI
from redis import Redis
import os, dotenv
import dspy
from chatdku.setup import setup, use_phoenix
from chatdku.config import config
from contextlib import asynccontextmanager
from .routes import chat


dotenv.load_dotenv()

app = FastAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):

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

    dspy.configure_cache(
    enable_disk_cache=True,
    enable_memory_cache=True,
    )

    yield

app = FastAPI(lifespan=lifespan)
app.include_router(chat.router, prefix="/api")

