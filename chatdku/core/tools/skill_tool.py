import json
import re
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from chatdku.config import config

logger = getLogger(__name__)

SKILLS_DIR = Path(config.skills_dir)
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
_NAMESPACE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def skills_list(category: Optional[str] = None) -> str:
    """
    List all available skills (progressive disclosure tier 1 - minimal metadata).

    Returns only name + description to minimize token usage. Use skill_view() to
    load full content, tags, related files, etc.

    Args:
        category: Optional category filter (e.g., "mlops")

    Returns:
        JSON string with minimal skill info: name, description, category
    """
    try:
        if not SKILLS_DIR.exists():
            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            raise FileNotFoundError(f"Skills directory not found: {SKILLS_DIR}")

        # Find all skills
        all_skills = _find_all_skills()

        if not all_skills:
            return json.dumps(
                {
                    "success": True,
                    "skills": [],
                    "categories": [],
                    "message": "No skills found in skills/ directory.",
                },
                ensure_ascii=False,
            )

        # Filter by category if specified
        if category:
            all_skills = [s for s in all_skills if s.get("category") == category]

        # Sort by category then name
        all_skills.sort(key=lambda s: (s.get("category") or "", s["name"]))

        # Extract unique categories
        categories = sorted(
            set(s.get("category") for s in all_skills if s.get("category"))
        )

        return json.dumps(
            {
                "success": True,
                "skills": all_skills,
                "categories": categories,
                "count": len(all_skills),
                "hint": "Use skill_view(name) to see full content, tags, and linked files",
            },
            ensure_ascii=False,
        )

    except Exception as e:
        raise e


def _find_all_skills() -> List[Dict[str, Any]]:
    """Recursively find all skills in ~/.hermes/skills/ and external dirs.
    Returns:
        List of skill metadata dicts (name, description, category).
    """
    skills = []
    seen_names: set = set()

    # Scan local dir first, then external dirs (local takes precedence)
    dirs_to_scan = []
    if SKILLS_DIR.exists():
        dirs_to_scan.append(SKILLS_DIR)

    for scan_dir in dirs_to_scan:
        for skill_md in scan_dir.rglob("SKILL.md"):
            skill_dir = skill_md.parent

            try:
                content = skill_md.read_text(encoding="utf-8")[:4000]
                frontmatter, body = parse_frontmatter(content)

                name = frontmatter.get("name", skill_dir.name)[:MAX_NAME_LENGTH]
                if name in seen_names:
                    continue

                description = frontmatter.get("description", "")
                if not description:
                    for line in body.strip().split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#"):
                            description = line
                            break

                if len(description) > MAX_DESCRIPTION_LENGTH:
                    description = description[: MAX_DESCRIPTION_LENGTH - 3] + "..."

                category = _get_category_from_path(skill_md)

                seen_names.add(name)
                skills.append(
                    {
                        "name": name,
                        "description": description,
                        "category": category,
                    }
                )

            except (UnicodeDecodeError, PermissionError) as e:
                logger.debug("Failed to read skill file %s: %s", skill_md, e)
                continue
            except Exception as e:
                logger.debug(
                    "Skipping skill at %s: failed to parse: %s",
                    skill_md,
                    e,
                    exc_info=True,
                )
                continue

    return skills


def yaml_load(content: str):
    """Parse YAML with lazy import and CSafeLoader preference."""
    loader = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
    return yaml.load(content, Loader=loader)


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown string.

    Uses yaml with CSafeLoader for full YAML support (nested metadata, lists)
    with a fallback to simple key:value splitting for robustness.

    Returns:
        (frontmatter_dict, remaining_body)
    """
    frontmatter: Dict[str, Any] = {}
    body = content

    if not content.startswith("---"):
        return frontmatter, body

    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return frontmatter, body

    yaml_content = content[3 : end_match.start() + 3]
    body = content[end_match.end() + 3 :]

    try:
        parsed = yaml_load(yaml_content)
        if isinstance(parsed, dict):
            frontmatter = parsed
    except Exception:
        # Fallback: simple key:value parsing for malformed YAML
        for line in yaml_content.strip().split("\n"):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    return frontmatter, body


def _get_category_from_path(skill_path: Path) -> Optional[str]:
    """
    Extract category from skill path based on directory structure.

    For paths like: ~/.hermes/skills/mlops/axolotl/SKILL.md -> "mlops"
    """
    # Try the module-level SKILLS_DIR first (respects monkeypatching in tests),
    dirs_to_check = [SKILLS_DIR]

    for skills_dir in dirs_to_check:
        try:
            rel_path = skill_path.relative_to(skills_dir)
            parts = rel_path.parts
            if len(parts) >= 3:
                return parts[0]
        except ValueError:
            continue
    return None


def parse_qualified_name(name: str) -> Tuple[Optional[str], str]:
    """Split ``'namespace:skill-name'`` into ``(namespace, bare_name)``.

    Returns ``(None, name)`` when there is no ``':'``.
    """
    if ":" not in name:
        return None, name
    return tuple(name.split(":", 1))  # type: ignore[return-value]


def is_valid_namespace(candidate: Optional[str]) -> bool:
    """Check whether *candidate* is a valid namespace (``[a-zA-Z0-9_-]+``)."""
    if not candidate:
        return False
    return bool(_NAMESPACE_RE.match(candidate))


def _parse_tags(tags_value) -> List[str]:
    """
    Parse tags from frontmatter value.

    Handles:
    - Already-parsed list (from yaml.safe_load): [tag1, tag2]
    - String with brackets: "[tag1, tag2]"
    - Comma-separated string: "tag1, tag2"

    Args:
        tags_value: Raw tags value — may be a list or string

    Returns:
        List of tag strings
    """
    if not tags_value:
        return []

    # yaml.safe_load already returns a list for [tag1, tag2]
    if isinstance(tags_value, list):
        return [str(t).strip() for t in tags_value if t]

    # String fallback — handle bracket-wrapped or comma-separated
    tags_value = str(tags_value).strip()
    if tags_value.startswith("[") and tags_value.endswith("]"):
        tags_value = tags_value[1:-1]

    return [t.strip().strip("\"'") for t in tags_value.split(",") if t.strip()]


def skill_view(name: str) -> str:
    """
    View the content of a skill or a specific file within a skill directory.

    Args:
        name: Name or path of the skill (e.g., "axolotl" or "03-fine-tuning/axolotl").
            Qualified names like "plugin:skill" resolve to plugin-provided skills.

    Returns:
        JSON string with skill content or error message
    """
    try:
        # ── Qualified name dispatch (plugin skills) ──────────────────
        # Names containing ':' are routed to the plugin skill registry.
        # Bare names fall through to the existing flat-tree scan below.
        if ":" in name:
            namespace, _ = parse_qualified_name(name)
            if not is_valid_namespace(namespace):
                return json.dumps(
                    {
                        "success": False,
                        "error": (
                            f"Invalid namespace '{namespace}' in '{name}'. "
                            f"Namespaces must match [a-zA-Z0-9_-]+."
                        ),
                    },
                    ensure_ascii=False,
                )

        # Build list of all skill directories to search
        all_dirs = []
        if SKILLS_DIR.exists():
            all_dirs.append(SKILLS_DIR)

        if not all_dirs:
            return json.dumps(
                {
                    "success": False,
                    "error": "Skills directory does not exist yet. It will be created on first install.",
                },
                ensure_ascii=False,
            )

        skill_dir = None
        skill_md = None

        # Search all dirs: local first, then external (first match wins)
        for search_dir in all_dirs:
            # Try direct path first (e.g., "mlops/axolotl")
            direct_path = search_dir / name
            if direct_path.is_dir() and (direct_path / "SKILL.md").exists():
                skill_dir = direct_path
                skill_md = direct_path / "SKILL.md"
                break
            elif direct_path.with_suffix(".md").exists():
                skill_md = direct_path.with_suffix(".md")
                break

        # Search by directory name across all dirs
        if not skill_md:
            for search_dir in all_dirs:
                for found_skill_md in search_dir.rglob("SKILL.md"):
                    if found_skill_md.parent.name == name:
                        skill_dir = found_skill_md.parent
                        skill_md = found_skill_md
                        break
                if skill_md:
                    break

        # Legacy: flat .md files
        if not skill_md:
            for search_dir in all_dirs:
                for found_md in search_dir.rglob(f"{name}.md"):
                    if found_md.name != "SKILL.md":
                        skill_md = found_md
                        break
                if skill_md:
                    break

        if not skill_md or not skill_md.exists():
            available = [s["name"] for s in _find_all_skills()[:20]]
            return json.dumps(
                {
                    "success": False,
                    "error": f"Skill '{name}' not found.",
                    "available_skills": available,
                    "hint": "Use skills_list to see all available skills",
                },
                ensure_ascii=False,
            )

        # Read the file once — reused for platform check and main content below
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception:
            raise Exception(f"Failed to read skill '{name}'")

        parsed_frontmatter: Dict[str, Any] = {}
        try:
            parsed_frontmatter, _ = parse_frontmatter(content)
        except Exception:
            parsed_frontmatter = {}

        # Reuse the parse from the platform check above
        frontmatter = parsed_frontmatter

        # Get reference, template, asset, and script files if this is a directory-based skill
        reference_files = []
        template_files = []
        asset_files = []
        script_files = []

        if skill_dir:
            references_dir = skill_dir / "references"
            if references_dir.exists():
                reference_files = [
                    str(f.relative_to(skill_dir)) for f in references_dir.glob("*.md")
                ]

            templates_dir = skill_dir / "templates"
            if templates_dir.exists():
                for ext in [
                    "*.md",
                    "*.py",
                    "*.yaml",
                    "*.yml",
                    "*.json",
                    "*.tex",
                    "*.sh",
                ]:
                    template_files.extend(
                        [
                            str(f.relative_to(skill_dir))
                            for f in templates_dir.rglob(ext)
                        ]
                    )

            # assets/ — agentskills.io standard directory for supplementary files
            assets_dir = skill_dir / "assets"
            if assets_dir.exists():
                for f in assets_dir.rglob("*"):
                    if f.is_file():
                        asset_files.append(str(f.relative_to(skill_dir)))

            scripts_dir = skill_dir / "scripts"
            if scripts_dir.exists():
                for ext in ["*.py", "*.sh", "*.bash", "*.js", "*.ts", "*.rb"]:
                    script_files.extend(
                        [str(f.relative_to(skill_dir)) for f in scripts_dir.glob(ext)]
                    )

        # Read tags/related_skills with backward compat:
        metadata = frontmatter.get("metadata")

        tags = _parse_tags(frontmatter.get("tags", ""))
        related_skills = _parse_tags(frontmatter.get("related_skills", ""))

        # Build linked files structure for clear discovery
        linked_files = {}
        if reference_files:
            linked_files["references"] = reference_files
        if template_files:
            linked_files["templates"] = template_files
        if asset_files:
            linked_files["assets"] = asset_files
        if script_files:
            linked_files["scripts"] = script_files

        try:
            rel_path = str(skill_md.relative_to(SKILLS_DIR))
        except ValueError:
            # External skill — use path relative to the skill's own parent dir
            rel_path = (
                str(skill_md.relative_to(skill_md.parent.parent))
                if skill_md.parent.parent
                else skill_md.name
            )
        skill_name = frontmatter.get(
            "name", skill_md.stem if not skill_dir else skill_dir.name
        )

        result = {
            "success": True,
            "name": skill_name,
            "description": frontmatter.get("description", ""),
            "tags": tags,
            "related_skills": related_skills,
            "content": content,
            "path": rel_path,
            "skill_dir": str(skill_dir) if skill_dir else None,
            "linked_files": linked_files if linked_files else None,
            "usage_hint": (
                "To view linked files, call skill_view(name, file_path) where file_path is e.g. 'references/api.md' or 'assets/config.yaml'"
                if linked_files
                else None
            ),
        }
        # Surface agentskills.io optional fields when present
        if frontmatter.get("compatibility"):
            result["compatibility"] = frontmatter["compatibility"]
        if isinstance(metadata, dict):
            result["metadata"] = metadata

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        raise e
