"""Plugin discovery and skill metadata contract tests."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PLUGIN_NAME = "self-driving-portfolio-skill"
VERSION = "0.2.0"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, block, _ = text.split("---", 2)
    return yaml.safe_load(block)


def test_plugin_manifests_are_consistent_and_resolvable():
    claude = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text())
    for manifest in (claude, codex):
        assert manifest["name"] == PLUGIN_NAME
        assert manifest["version"] == VERSION
        assert manifest["license"] == "MIT"
    discovered_skills = sorted((REPO / "skills").glob("*/SKILL.md"))
    assert len(discovered_skills) == 7

    claude_market = json.loads(
        (REPO / ".claude-plugin" / "marketplace.json").read_text()
    )
    codex_market = json.loads(
        (REPO / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    assert claude_market["plugins"][0]["name"] == PLUGIN_NAME
    assert claude_market["plugins"][0]["version"] == VERSION
    assert codex_market["plugins"][0]["name"] == PLUGIN_NAME


def test_skill_frontmatter_has_specific_supported_metadata():
    skill_files = [REPO / "SKILL.md", *sorted((REPO / "skills").glob("*/SKILL.md"))]
    for path in skill_files:
        metadata = _frontmatter(path)
        assert set(metadata) == {"name", "description"}
        assert metadata["name"]
        assert metadata["description"].startswith("This skill should be used when")
        assert len(metadata["description"]) <= 300


def test_command_frontmatter_is_complete():
    commands = sorted((REPO / "commands").glob("*.md"))
    assert len(commands) == 4
    for path in commands:
        metadata = _frontmatter(path)
        assert metadata["description"]
        assert "argument-hint" in metadata
        assert metadata["allowed-tools"]


def test_agent_frontmatter_is_triggerable_and_least_privilege():
    agents = sorted((REPO / "agents").glob("*.md"))
    assert len(agents) == 6
    colors = set()
    for path in agents:
        metadata = _frontmatter(path)
        assert path.stem == metadata["name"]
        assert metadata["description"].startswith("Use this agent when")
        assert metadata["description"].count("<example>") >= 2
        assert metadata["model"] == "inherit"
        assert metadata["tools"] == ["Read", "Grep", "Glob", "Bash"]
        colors.add(metadata["color"])
    assert len(colors) == len(agents)
