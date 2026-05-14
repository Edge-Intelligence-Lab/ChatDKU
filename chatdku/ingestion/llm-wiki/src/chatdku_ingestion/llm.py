from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from chatdku.config import config


@dataclass(slots=True)
class LLMWikiWriter:
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout: int = 120

    def __post_init__(self) -> None:
        self.model = self.model or config.llm
        self.base_url = (self.base_url or config.llm_url).rstrip("/")
        self.api_key = self.api_key or config.llm_api_key or "EMPTY"

    def _chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
        wrapped_system_prompt = (
            system_prompt
            + " Return exactly one concise answer. "
            + "Start the answer with 'Final answer:' and include no extra sections."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": wrapped_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "top_p": 0.8,
            "presence_penalty": 0.0,
            "enable_thinking": False,
            "extra_body": {
                "top_k": 20,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return self._clean_answer(content)
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            return self._clean_answer(reasoning.strip().split("\n\n")[-1].strip())
        raise ValueError(f"Unexpected LLM response format: {data}")

    @staticmethod
    def _clean_answer(text: str) -> str:
        cleaned = text.strip()
        prefix = "Final answer:"
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
        suspicious_markers = [
            "Analyze User Input",
            "Analyze the Goal",
            "Deconstruct the Request",
            "Identify Constraints",
            "thinking process",
            "**",
        ]
        if any(marker in cleaned for marker in suspicious_markers):
            raise ValueError(f"LLM returned reasoning-style output: {cleaned[:200]}")
        return cleaned

    def write_cluster_summary(self, cluster_title: str, topic_families: list[str], sources: list[dict]) -> str:
        system_prompt = (
            "You are writing a compact wiki source-cluster summary for ChatDKU. "
            "This wiki is a natural-language index, not a bulletin rewrite. "
            "Write exactly 2 concise sentences. Focus on what the cluster is about, "
            "what kinds of source surfaces it combines, and why a reader would open it. "
            "Do not invent details not present in the provided metadata. "
            "Do not explain your reasoning."
        )
        source_lines = []
        for source in sources:
            source_lines.append(
                f"- {source['file_name']} | {source['source_type']} | {source['last_modified'] or 'unknown_date'}"
            )
        user_prompt = (
            f"Cluster title: {cluster_title}\n"
            f"Topic families: {', '.join(topic_families)}\n"
            "Sample sources:\n"
            + "\n".join(source_lines)
        )
        return self._chat(system_prompt, user_prompt, max_tokens=120)

    def write_topic_summary(
        self,
        topic_title: str,
        topic_families: list[str],
        cluster_status: str,
        preferred_sources: list[str],
    ) -> str:
        system_prompt = (
            "You are writing a compact topic-index summary for ChatDKU. "
            "This page is read before the detailed source documents. "
            "Write exactly 2 short sentences that orient the reader and indicate that this page routes to the best source cluster. "
            "Do not restate detailed policy rules. Do not explain your reasoning."
        )
        user_prompt = (
            f"Topic title: {topic_title}\n"
            f"Topic families: {', '.join(topic_families)}\n"
            f"Cluster status: {cluster_status}\n"
            "Preferred detailed sources:\n"
            + "\n".join(f"- {source}" for source in preferred_sources[:3])
        )
        return self._chat(system_prompt, user_prompt, max_tokens=100)
