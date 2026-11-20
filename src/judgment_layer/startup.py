"""Install and remove project guidance loaded at agent session start."""
import json
import os
import stat
import tempfile
from pathlib import Path

from .model import JudgmentError
from .setup import AGENTS, check_path

START = "<!-- proofpress:startup:start -->"
END = "<!-- proofpress:startup:end -->"


def read_manifest(store, root):
    path = store / "startup.json"
    check_path(path, root)
    return json.loads(path.read_text()) if path.exists() else {}


def plan_startup(root, store, agents):
    override = root / "AGENTS.override.md"
    codex_path = "AGENTS.md"
    if "codex" in agents and (override.exists() or override.is_symlink()):
        check_path(override, root)
        if override.read_bytes().strip():
            codex_path = override.name
    paths = {"codex": codex_path, "claude-code": ".claude/rules/proofpress.md",
             "cursor": ".cursor/rules/proofpress.mdc"}
    manifest = read_manifest(store, root)
    changes = {}
    selected = []
    for agent in agents:
        if agent not in paths:
            continue
        path = root / paths[agent]
        check_path(path, root)
        before = path.read_bytes() if path.exists() else None
        previous = manifest.get(str(path), {})
        old = previous.get("text", "").encode()
        skill = AGENTS[agent] + "/proofpress/SKILL.md"
        text = (
            "## Proofpress judgment workflow\n\n"
            f"Read `{skill}` for this project's judgment workflow. "
            "Use applicable approved judgments before related work. Propose consequential "
            "human or agent judgments with their reasons, sources and conditions. "
            "Leave admission and enforcement to the human owner.\n\n"
            "If `proofpress` is outside PATH, locate it with `uv tool dir --bin` "
            "or `~/.local/bin/uv tool dir --bin`.\n"
        )
        shared = agent == "codex"
        if shared:
            text = f"\n\n{START}\n{text}{END}\n"
        elif agent == "cursor":
            text = "---\ndescription: Proofpress judgment workflow\nalwaysApply: true\n---\n\n" + text
        expected = text.encode()
        if shared:
            base = before or b""
            if START.encode() in base or END.encode() in base:
                managed = expected if base.count(expected) == 1 else old
                if (not managed or base.count(managed) != 1
                        or base.count(START.encode()) != 1 or base.count(END.encode()) != 1):
                    raise JudgmentError(f"Proofpress startup block was edited: {path}")
                after = base.replace(managed, expected, 1)
            else:
                after = base + expected
        else:
            if before is not None and before not in (expected, old):
                raise JudgmentError(f"Existing startup file differs: {path}")
            after = expected
        changes[path] = (before, after)
        manifest[str(path)] = {"text": text, "shared": shared,
                               "created": previous.get("created", before is None)}
        selected.append(str(path))
    return changes, manifest, selected


def apply_changes(changes):
    for path, (before, _) in changes.items():
        actual = path.read_bytes() if path.exists() else None
        if actual != before:
            raise JudgmentError(f"Startup file changed during setup: {path}")
    for path, (before, after) in changes.items():
        if before == after:
            continue
        if after is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=".proofpress-")
        try:
            with os.fdopen(fd, "wb") as temp:
                temp.write(after)
            if before is not None:
                os.chmod(name, stat.S_IMODE(path.stat().st_mode))
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)


def plan_removal(store, root):
    manifest = read_manifest(store, root)
    changes = {}
    preserved = {}
    for name, entry in manifest.items():
        path = Path(name)
        if not path.is_relative_to(root) or ".." in path.parts:
            raise JudgmentError("Startup manifest belongs to another project")
        check_path(path, root)
        if not path.exists():
            continue
        before = path.read_bytes()
        expected = entry["text"].encode()
        if entry["shared"] and before.count(expected) == 1:
            after = before.replace(expected, b"", 1)
            changes[path] = (before, None if not after and entry["created"] else after)
        elif not entry["shared"] and before == expected:
            changes[path] = (before, None)
        else:
            preserved[name] = entry
    return changes, preserved
