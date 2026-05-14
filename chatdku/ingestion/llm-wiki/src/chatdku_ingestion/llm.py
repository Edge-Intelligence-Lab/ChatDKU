from __future__ import annotations

import json
import re
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
            + " Return exactly one answer block wrapped in <answer> and </answer>. "
            + "Do not output anything before <answer> or after </answer>."
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
        finish_reason = data["choices"][0].get("finish_reason")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return self._clean_answer(content, finish_reason=finish_reason)
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            return self._clean_answer(reasoning, finish_reason=finish_reason)
        raise ValueError(f"Unexpected LLM response format: {data}")

    @staticmethod
    def _clean_answer(text: str, *, finish_reason: str | None = None) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.S | re.I).strip()

        answer_match = re.search(r"<answer>\s*(.*?)\s*</answer>", cleaned, flags=re.I | re.S)
        if answer_match:
            cleaned = answer_match.group(1).strip()
        else:
            final_answer_matches = re.findall(
                r"Final answer:\s*(.*)",
                cleaned,
                flags=re.I | re.S,
            )
            if final_answer_matches:
                cleaned = final_answer_matches[-1].strip()

        # If Qwen leaks a structured reasoning preamble, keep only the tail after the
        # last numbered block if it looks like a final short answer.
        if "\n\n" in cleaned and any(
            marker in cleaned
            for marker in [
                "thinking process",
                "Analyze User Input",
                "Analyze the Goal",
                "Deconstruct the Request",
                "Identify Constraints",
            ]
        ):
            tail = cleaned.split("\n\n")[-1].strip()
            if tail and len(tail) < len(cleaned):
                cleaned = tail

        suspicious_markers = [
            "Analyze User Input",
            "Analyze the Goal",
            "Deconstruct the Request",
            "Identify Constraints",
            "thinking process",
            "<think>",
        ]
        if finish_reason == "length" and not answer_match:
            raise ValueError("LLM response hit token limit before emitting an <answer> block")
        if any(marker in cleaned for marker in suspicious_markers):
            raise ValueError(f"LLM returned reasoning-style output: {cleaned[:200]}")
        return cleaned

    def _chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        required_keys: list[str],
        max_tokens: int = 500,
    ) -> dict:
        prompt = (
            system_prompt
            + " Return exactly one <answer> JSON object with double-quoted keys and no markdown."
        )
        cleaned = self._chat(prompt, user_prompt, max_tokens=max_tokens)
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object, got: {type(payload)!r}")
        for key in required_keys:
            payload.setdefault(key, [])
        return payload

    def write_cluster_summary(self, cluster_title: str, topic_families: list[str], sources: list[dict]) -> str:
        system_prompt = (
            "You are writing a compact wiki source-cluster summary for ChatDKU. "
            "This wiki is a natural-language index, not a bulletin rewrite. "
            "Write exactly 2 concise sentences. Focus on what the cluster is about, "
            "what kinds of source surfaces it combines, and why a reader would open it. "
            "Do not invent details not present in the provided metadata. "
            "Do not explain your reasoning. Keep the answer under 55 words."
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
        return self._chat(system_prompt, user_prompt, max_tokens=320)

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
            "Do not restate detailed policy rules. Do not explain your reasoning. Keep the answer under 45 words."
        )
        user_prompt = (
            f"Topic title: {topic_title}\n"
            f"Topic families: {', '.join(topic_families)}\n"
            f"Cluster status: {cluster_status}\n"
            "Preferred detailed sources:\n"
            + "\n".join(f"- {source}" for source in preferred_sources[:3])
        )
        return self._chat(system_prompt, user_prompt, max_tokens=280)

    def review_topic_maintenance(
        self,
        *,
        topic_id: str,
        topic_title: str,
        topic_summary: str,
        topic_families: list[str],
        cluster_status: str,
        preferred_sources: list[str],
        authority_sources: list[str],
        related_candidates: list[dict],
    ) -> dict:
        system_prompt = (
            "You are reviewing a DKU wiki topic index for maintenance. "
            "This wiki is a natural-language index, not the source of truth. "
            "Inspect structure only: weak interconnection, likely overlap, conflict signals, or missing routing context. "
            "Do not rewrite detailed policies. "
            "Return a compact JSON object."
        )
        candidate_lines = []
        for candidate in related_candidates[:8]:
            candidate_lines.append(
                f"- page_id: {candidate['page_id']} | title: {candidate['title']} | families: {', '.join(candidate['topic_families'])}"
            )
        user_prompt = (
            f"Topic page id: {topic_id}\n"
            f"Topic title: {topic_title}\n"
            f"Current summary: {topic_summary}\n"
            f"Topic families: {', '.join(topic_families)}\n"
            f"Cluster status: {cluster_status}\n"
            "Preferred detailed sources:\n"
            + "\n".join(f"- {item}" for item in preferred_sources[:3])
            + "\nAuthority sources:\n"
            + ("\n".join(f"- {item}" for item in authority_sources[:2]) or "- none")
            + "\nRelated topic candidates:\n"
            + ("\n".join(candidate_lines) or "- none")
            + "\nReturn JSON with keys "
            + '"maintenance_notes", "open_questions", "link_suggestions", "conflict_signals". '
            + "Each value must be a JSON array. "
            + '"link_suggestions" must use page_id values from the candidate list only.'
        )
        return self._chat_json(
            system_prompt,
            user_prompt,
            required_keys=[
                "maintenance_notes",
                "open_questions",
                "link_suggestions",
                "conflict_signals",
            ],
            max_tokens=700,
        )
