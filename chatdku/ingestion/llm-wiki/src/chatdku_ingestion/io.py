from __future__ import annotations

import json
from pathlib import Path


def load_nodes(nodes_path: str | Path) -> list[dict]:
    path = Path(nodes_path)
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise ValueError("nodes.json must be a list")
    return payload


def ensure_layout(base_dir: str | Path) -> dict[str, Path]:
    base = Path(base_dir)
    wiki_dir = base / "wiki"
    paths = {
        "root": base,
        "wiki": wiki_dir,
        "topics": wiki_dir / "topics",
        "clusters": wiki_dir / "clusters",
        "services": wiki_dir / "services",
        "timelines": wiki_dir / "timelines",
        "graph": base / "graph",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def clear_markdown_dir(path: Path) -> None:
    if not path.exists():
        return
    for child in path.glob("*.md"):
        child.unlink()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
