"""Tests for chatdku/core/tools/skill_tool.py."""

import json
from pathlib import Path

import pytest

from chatdku.core.tools import skill_tool
from chatdku.core.tools.skill_tool import (
    _find_all_skills,
    _get_category_from_path,
    _parse_tags,
    is_valid_namespace,
    parse_frontmatter,
    parse_qualified_name,
    skill_view,
    skills_list,
    yaml_load,
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    """Redirect SKILLS_DIR to a temporary directory."""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(skill_tool, "SKILLS_DIR", skills_root)
    return skills_root


def _write_skill(
    skills_root: Path,
    rel_dir: str,
    name: str,
    description: str = "",
    body: str = "Body content.",
    extra_frontmatter: str = "",
) -> Path:
    """Create a SKILL.md-based skill. Returns the skill directory."""
    skill_dir = skills_root / rel_dir
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm_lines = [f"name: {name}"]
    if description:
        fm_lines.append(f"description: {description}")
    if extra_frontmatter:
        fm_lines.append(extra_frontmatter.strip())
    frontmatter = "\n".join(fm_lines)
    content = f"---\n{frontmatter}\n---\n{body}\n"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


# ──────────────────────────────────────────────────────────────────────
# parse_frontmatter / yaml_load
# ──────────────────────────────────────────────────────────────────────


def test_parse_frontmatter_valid():
    content = "---\nname: foo\ndescription: bar\n---\nBody text\n"
    fm, body = parse_frontmatter(content)
    assert fm == {"name": "foo", "description": "bar"}
    assert body.strip() == "Body text"


def test_parse_frontmatter_no_frontmatter():
    content = "Just a body, no frontmatter."
    fm, body = parse_frontmatter(content)
    assert fm == {}
    assert body == content


def test_parse_frontmatter_no_closing_delimiter():
    content = "---\nname: foo\nBody without closing"
    fm, body = parse_frontmatter(content)
    assert fm == {}
    assert body == content


def test_parse_frontmatter_handles_list():
    content = "---\nname: foo\ntags:\n  - a\n  - b\n---\nBody\n"
    fm, _ = parse_frontmatter(content)
    assert fm["tags"] == ["a", "b"]


def test_parse_frontmatter_fallback_on_malformed_yaml(monkeypatch):
    """When yaml parsing fails, fallback to simple key:value parsing."""

    def broken_yaml_load(_content):
        raise ValueError("broken")

    monkeypatch.setattr(skill_tool, "yaml_load", broken_yaml_load)
    content = "---\nname: foo\ndescription: bar\n---\nBody\n"
    fm, _ = parse_frontmatter(content)
    assert fm == {"name": "foo", "description": "bar"}


def test_yaml_load_basic():
    assert yaml_load("a: 1\nb: 2\n") == {"a": 1, "b": 2}


# ──────────────────────────────────────────────────────────────────────
# parse_qualified_name / is_valid_namespace
# ──────────────────────────────────────────────────────────────────────


def test_parse_qualified_name_with_namespace():
    ns, bare = parse_qualified_name("plugin:skill-name")
    assert ns == "plugin"
    assert bare == "skill-name"


def test_parse_qualified_name_bare():
    ns, bare = parse_qualified_name("skill-name")
    assert ns is None
    assert bare == "skill-name"


@pytest.mark.parametrize(
    "candidate,expected",
    [
        ("plugin", True),
        ("plugin-1", True),
        ("plugin_1", True),
        ("Plugin123", True),
        ("bad ns", False),
        ("bad/ns", False),
        ("", False),
        (None, False),
    ],
)
def test_is_valid_namespace(candidate, expected):
    assert is_valid_namespace(candidate) is expected


# ──────────────────────────────────────────────────────────────────────
# _parse_tags
# ──────────────────────────────────────────────────────────────────────


def test_parse_tags_empty():
    assert _parse_tags("") == []
    assert _parse_tags(None) == []


def test_parse_tags_from_list():
    assert _parse_tags(["a", "b", ""]) == ["a", "b"]


def test_parse_tags_bracket_string():
    assert _parse_tags("[a, b, c]") == ["a", "b", "c"]


def test_parse_tags_comma_string():
    assert _parse_tags("a, b, c") == ["a", "b", "c"]


def test_parse_tags_strips_quotes():
    assert _parse_tags('"a", \'b\'') == ["a", "b"]


# ──────────────────────────────────────────────────────────────────────
# _get_category_from_path
# ──────────────────────────────────────────────────────────────────────


def test_get_category_from_path_with_category(skills_dir):
    skill_md = skills_dir / "mlops" / "axolotl" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("stub")
    assert _get_category_from_path(skill_md) == "mlops"


def test_get_category_from_path_shallow(skills_dir):
    skill_md = skills_dir / "axolotl" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("stub")
    assert _get_category_from_path(skill_md) is None


def test_get_category_from_path_outside_skills_dir(tmp_path, skills_dir):
    external = tmp_path / "elsewhere" / "cat" / "skill" / "SKILL.md"
    external.parent.mkdir(parents=True)
    external.write_text("stub")
    assert _get_category_from_path(external) is None


# ──────────────────────────────────────────────────────────────────────
# _find_all_skills
# ──────────────────────────────────────────────────────────────────────


def test_find_all_skills_empty(skills_dir):
    assert _find_all_skills() == []


def test_find_all_skills_finds_skill(skills_dir):
    _write_skill(skills_dir, "mlops/axolotl", "axolotl", "fine-tune models")
    skills = _find_all_skills()
    assert len(skills) == 1
    assert skills[0]["name"] == "axolotl"
    assert skills[0]["description"] == "fine-tune models"
    assert skills[0]["category"] == "mlops"


def test_find_all_skills_description_falls_back_to_body(skills_dir):
    skill_dir = skills_dir / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: foo\n---\n# Heading\n\nActual description line.\n",
        encoding="utf-8",
    )
    skills = _find_all_skills()
    assert skills[0]["description"] == "Actual description line."


def test_find_all_skills_deduplicates_by_name(skills_dir):
    _write_skill(skills_dir, "a/dup", "dup", "first")
    _write_skill(skills_dir, "b/dup", "dup", "second")
    skills = _find_all_skills()
    assert len(skills) == 1


def test_find_all_skills_truncates_long_description(skills_dir):
    long_desc = "x" * (skill_tool.MAX_DESCRIPTION_LENGTH + 50)
    _write_skill(skills_dir, "foo", "foo", long_desc)
    skills = _find_all_skills()
    assert len(skills[0]["description"]) == skill_tool.MAX_DESCRIPTION_LENGTH
    assert skills[0]["description"].endswith("...")


# ──────────────────────────────────────────────────────────────────────
# skills_list
# ──────────────────────────────────────────────────────────────────────


def test_skills_list_empty(skills_dir):
    result = json.loads(skills_list())
    assert result["success"] is True
    assert result["skills"] == []
    assert "No skills found" in result["message"]


def test_skills_list_returns_skills(skills_dir):
    _write_skill(skills_dir, "mlops/axolotl", "axolotl", "fine-tune")
    _write_skill(skills_dir, "web/react", "react", "react stuff")
    result = json.loads(skills_list())
    assert result["success"] is True
    assert result["count"] == 2
    names = [s["name"] for s in result["skills"]]
    assert "axolotl" in names and "react" in names
    assert sorted(result["categories"]) == ["mlops", "web"]


def test_skills_list_category_filter(skills_dir):
    _write_skill(skills_dir, "mlops/axolotl", "axolotl", "ml")
    _write_skill(skills_dir, "web/react", "react", "web")
    result = json.loads(skills_list(category="mlops"))
    assert result["count"] == 1
    assert result["skills"][0]["name"] == "axolotl"


def test_skills_list_raises_when_dir_missing(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(skill_tool, "SKILLS_DIR", missing)
    with pytest.raises(FileNotFoundError):
        skills_list()
    # side effect: the function creates the missing directory before raising
    assert missing.exists()


# ──────────────────────────────────────────────────────────────────────
# skill_view
# ──────────────────────────────────────────────────────────────────────


def test_skill_view_invalid_namespace(skills_dir):
    result = json.loads(skill_view("bad ns:skill"))
    assert result["success"] is False
    assert "Invalid namespace" in result["error"]


def test_skill_view_returns_error_when_dir_missing(tmp_path, monkeypatch):
    missing = tmp_path / "nope"
    monkeypatch.setattr(skill_tool, "SKILLS_DIR", missing)
    result = json.loads(skill_view("anything"))
    assert result["success"] is False
    assert "Skills directory does not exist" in result["error"]


def test_skill_view_skill_not_found(skills_dir):
    _write_skill(skills_dir, "foo", "foo", "foo desc")
    result = json.loads(skill_view("nonexistent"))
    assert result["success"] is False
    assert "not found" in result["error"]
    assert "foo" in result["available_skills"]


def test_skill_view_direct_path(skills_dir):
    _write_skill(skills_dir, "mlops/axolotl", "axolotl", "fine-tune")
    result = json.loads(skill_view("mlops/axolotl"))
    assert result["success"] is True
    assert result["name"] == "axolotl"
    assert result["description"] == "fine-tune"
    assert "fine-tune" in result["content"] or "axolotl" in result["content"]
    assert result["linked_files"] is None


def test_skill_view_by_bare_dir_name(skills_dir):
    _write_skill(skills_dir, "mlops/axolotl", "axolotl", "fine-tune")
    result = json.loads(skill_view("axolotl"))
    assert result["success"] is True
    assert result["name"] == "axolotl"


def test_skill_view_legacy_flat_md(skills_dir):
    (skills_dir / "legacy.md").write_text(
        "---\nname: legacy\ndescription: legacy skill\n---\nBody\n",
        encoding="utf-8",
    )
    result = json.loads(skill_view("legacy"))
    assert result["success"] is True
    assert result["name"] == "legacy"


def test_skill_view_linked_files(skills_dir):
    skill_dir = _write_skill(skills_dir, "mlops/axolotl", "axolotl", "fine-tune")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "api.md").write_text("# API")
    (skill_dir / "templates").mkdir()
    (skill_dir / "templates" / "config.yaml").write_text("k: v")
    (skill_dir / "assets").mkdir()
    (skill_dir / "assets" / "logo.png").write_bytes(b"\x89PNG")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('hi')")

    result = json.loads(skill_view("axolotl"))
    linked = result["linked_files"]
    assert linked is not None
    assert linked["references"] == ["references/api.md"]
    assert linked["templates"] == ["templates/config.yaml"]
    assert linked["assets"] == ["assets/logo.png"]
    assert linked["scripts"] == ["scripts/run.py"]
    assert result["usage_hint"] is not None


def test_skill_view_parses_tags_and_related(skills_dir):
    _write_skill(
        skills_dir,
        "foo",
        "foo",
        "desc",
        extra_frontmatter="tags:\n  - alpha\n  - beta\nrelated_skills: [bar, baz]",
    )
    result = json.loads(skill_view("foo"))
    assert result["tags"] == ["alpha", "beta"]
    assert result["related_skills"] == ["bar", "baz"]


def test_skill_view_surfaces_optional_fields(skills_dir):
    _write_skill(
        skills_dir,
        "foo",
        "foo",
        "desc",
        extra_frontmatter="compatibility: claude-4\nmetadata:\n  version: 1\n  author: test",
    )
    result = json.loads(skill_view("foo"))
    assert result["compatibility"] == "claude-4"
    assert result["metadata"] == {"version": 1, "author": "test"}
