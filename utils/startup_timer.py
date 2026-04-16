#!/usr/bin/env python3
"""Startup timing diagnostic — identifies slow initialization steps."""
import os
import time

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

_t0 = time.perf_counter()


def lap(label: str, t_prev: float) -> float:
    t = time.perf_counter()
    print(f"  {t - t_prev:6.2f}s  {label}")
    return t


print("=== ChatDKU startup timer ===")
t = _t0

# --- imports ---
print("\n[imports]")

import dspy; t = lap("import dspy", t)  # noqa: E402,E401
from chatdku.config import config; t = lap("import config", t)  # noqa: E402,E401

from chatdku.core.tools.retriever.keyword_retriever import KeywordRetriever; t = lap("import KeywordRetriever (+ NLTK check)", t)  # noqa: E402,E401,E501
from chatdku.core.tools.retriever.vector_retriever import VectorRetriever; t = lap("import VectorRetriever (+ chromadb)", t)  # noqa: E402,E401,E501
from chatdku.core.tools.major_requirements import MajorRequirementsLookupOuter; t = lap("import MajorRequirementsLookupOuter", t)  # noqa: E402,E401,E501
from chatdku.core.tools.syllabi_tool.query_curriculum_db import QueryCurriculumOuter; t = lap("import QueryCurriculumOuter (+ DB)", t)  # noqa: E402,E401,E501
from chatdku.core.tools.get_prerequisites import PrerequisiteLookupOuter; t = lap("import PrerequisiteLookupOuter", t)  # noqa: E402,E401,E501
from chatdku.core.tools.course_schedule import CourseScheduleLookupOuter; t = lap("import CourseScheduleLookupOuter", t)  # noqa: E402,E401,E501
from chatdku.setup import setup, use_phoenix; t = lap("import setup, use_phoenix", t)  # noqa: E402,E401

# --- initialization ---
print("\n[initialization]")

setup(); t = lap("setup() — embed model + tokenizer", t)
use_phoenix(); t = lap("use_phoenix() — OTel register", t)

lm = dspy.LM(
    model="openai/" + config.backup_llm,
    api_base=config.backup_llm_url,
    api_key=config.llm_api_key,
    model_type="chat",
    max_tokens=config.output_window,
    temperature=config.llm_temperature,
)
dspy.configure(lm=lm)
t = lap("dspy.LM() + configure()", t)

user_id = "Chat_DKU"
KeywordRetriever(retriever_top_k=10, user_id=user_id, search_mode=0, files=[])
t = lap("KeywordRetriever() init", t)

VectorRetriever(retriever_top_k=10, user_id=user_id, search_mode=0, files=[])
t = lap("VectorRetriever() init", t)

MajorRequirementsLookupOuter(config.major_requirements_dir)
t = lap("MajorRequirementsLookupOuter() init", t)

QueryCurriculumOuter()
t = lap("QueryCurriculumOuter() init (DB connect + schema fetch)", t)

print(f"\n=== total: {t - _t0:.2f}s ===")
