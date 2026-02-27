from bs4 import BeautifulSoup
from openai import OpenAI
import os
import json
import time
import asyncio
import functools
import hashlib
from ChatDKU.chatdku.chatdku.config import config


LLM = config.llm
LLM_URL = config.llm_url
LLM_API_KEY = ""

client = OpenAI(
    base_url=LLM_URL,
    api_key=LLM_API_KEY
)

PROMPT_TEMPLATE=(
    "Return ONLY a single word: keep or drop.\n"
    "You are a 'strict' web content filter for students in Duke Kunshan University (DKU).\n"
    "Your task: Decide if the given page is **LONG-TERM USEFUL** for DKU students.\n" \
    "RULES:\n" 
    "- Be as STRICT as possible. Default to dropping pages unless they clearly match the useful criteria.\n"
    "- Only keep pages that are directly and permanently helpful to DKU students.\n"
    "KEEP ONLY if the page is one of these:\n"
    "1. Official department / academic program / athletics introduction / career development or home pages.\n"
    "2. Technical or how-to guides (IT, VPN, Library login, course-registration instructions).\n"
    "3. Appointment, services or resource-booking portals that students regularly need.\n"
    "\n"
    "DROP if the page is any of these (or similar):\n"
    "- News, announcements, sharing stories, competitions, temporary notices, events, workshops.\n"
    "- Empty pages, placeholder pages, login or sign-up screens.\n"
    "- Anything not clearly and permanently useful to students.\n"
    "Return ONLY a single word: keep or drop.\n"
    "URL: {url}\n"
    "Content snippet (truncated):\n{snippet}"
)


def html_to_text(html):
    # print("[DEBUG] Calling html_to_text")
    soup = BeautifulSoup(html, "html.parser")
    # 去掉 script/style
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # 压缩空白
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # print("[DEBUG]",lines[:10])
    return "\n".join(lines)

def parse_llm_decision(raw: str) -> str:
    """
    Robustly parse LLM output to extract final keep/drop decision.
    - Only the LAST non-empty line matters
    - Strip thinking content
    - Fail-safe: default to DROP
    """
    if not raw:
        return "drop"

    # remove <think> tags or similar garbage
    cleaned = raw.replace("<think>", "").replace("</think>", "").strip()

    # split into lines and only check last meaningful line
    lines = [line.strip().lower() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return "drop"
    
    last_line = lines[-1]  # Real final answer should be here

    # reduce noise like "answer: keep", "**drop**", etc.
    tokens = last_line.replace("*", "").replace("answer:", "").strip()
    print(tokens)

    if tokens == "keep":
        return "keep"
    if tokens == "drop":
        return "drop"

    # extra safety: exact word match only
    if tokens.startswith("keep"):
        return "keep"
    if tokens.startswith("drop"):
        return "drop"

    print(f"[LLM FILTER WARNING] Failed to parse decision from: {raw}")
    return "drop"

class RateLimiter:
    def __init__(self, rate_per_sec: float):
        self.interval = 1.0 / rate_per_sec
        self.lock = asyncio.Lock()
        self.last_time = 0.0

    async def wait(self):
        async with self.lock:
            now = time.monotonic()
            wait_time = self.interval - (now - self.last_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_time = time.monotonic()

rate_limiter = RateLimiter(rate_per_sec=0.3)

async def filter_page(html: str, url: str, args) -> bool:
    # print(f"[DEBUG] filter_page called for {url}")
    # cache.clear
    if not args.use_llm:
        return True
    # 缓存键
    # cache_key = hashlib.sha1((url + html[:1000]).encode()).hexdigest()
    # if cache_key in cache:
    #     print(f"Cache hit for {url}: {cache[cache_key]}")
    #     return cache[cache_key]

    # 截断
    full_text = html_to_text(html)
    snippet = full_text[:300]
    prompt = PROMPT_TEMPLATE.format(url=url, snippet=snippet)
    # 速率限制
    await rate_limiter.wait()
    try:
        print(f"[LLM FILTER] calling LLM on page length {len(html)}")
        resp = await asyncio.to_thread(
            functools.partial(
                client.chat.completions.create,
                model=LLM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0,
            )
        )
        # print("[LLM RAW]", resp)
        msg = resp.choices[0].message.content
        llm_result = parse_llm_decision(msg)
        return llm_result == "keep"
    except Exception as e:
        print(f"[Filter Error] {url}: {e}")
        return True  # 出错默认保留
