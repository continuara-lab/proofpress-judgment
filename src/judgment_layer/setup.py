"""Project-local skill installation, with no host config edits or owner actions."""
import shlex
import json
import hashlib
import uuid
from importlib.resources import files
from pathlib import Path

from .model import JudgmentError
from .store import Store, initialize


# Prefer the interoperable directory where documented. All adapters use the
# same instructions and store; these are discovery paths, not runtime gates.
AGENTS = {
    "codex": ".agents/skills",
    "cursor": ".agents/skills",
    "devin": ".agents/skills",  # Devin CLI / Local, not automatic Cloud setup
    "grok": ".agents/skills",  # Grok Build, not grok.com chat
    "gemini": ".agents/skills",  # Gemini CLI
    "hermes": ".agents/skills",
    "openclaw": ".agents/skills",  # Run setup in the selected agent workspace
    "copilot": ".agents/skills",  # Copilot CLI
    "opencode": ".agents/skills",
    "claude-code": ".claude/skills",
    "cline": ".claude/skills",  # Documented compatibility directory
    "windsurf": ".windsurf/skills",
}


def check_path(path, root):
    """Do not follow preexisting symlinks or write through non-directories."""
    for entry in [path, *path.parents]:
        if entry == root:
            break
        if entry.is_symlink():
            raise JudgmentError(f"Refusing symlink in setup path: {entry}")
        if entry != path and entry.exists() and not entry.is_dir():
            raise JudgmentError(f"Setup parent is not a directory: {entry}")


def setup(project, workspace, agents, owner=None, dry_run=False, upgrade=False):
    root = Path(project).resolve()
    if not root.is_dir():
        raise JudgmentError("Project must be an existing directory")
    if not agents or any(agent not in AGENTS for agent in agents):
        raise JudgmentError("Select documented agents with --agents or --all")
    selected = sorted(set(agents))
    store = Path(workspace).expanduser()
    store = store if store.is_absolute() else root / store
    # Setup is project-local. Use init separately for an external store.
    if not store.is_relative_to(root) or ".." in store.parts:
        raise JudgmentError("Setup workspace must be inside the selected project")
    check_path(store, root)
    if store.exists():
        existing = Store(store)
        try:
            existing.audit()
            config = existing.config
        finally:
            existing.close()
        if owner is not None and owner != config["owner"]:
            raise JudgmentError("Existing workspace owner differs; setup never changes policy")
    elif not dry_run and owner is None:
        raise JudgmentError("A new workspace requires --owner human:<name>; admission remains manual")
    if owner is not None and (not owner.startswith("human:") or not owner[6:].strip()):
        raise JudgmentError("Use --owner human:<name>")

    for directory in {AGENTS[agent] for agent in selected}:
        legacy = root / directory / "judgment-layer"
        if legacy.exists() or legacy.is_symlink():
            raise JudgmentError(f"Legacy skill found: {legacy}. Back it up outside the skill directory before setup; no files changed.")

    source = files("judgment_layer")
    bundle = source.joinpath("skill")
    content = bundle.joinpath("SKILL.md").read_text().replace(
        "{{WORKSPACE_ARGUMENT}}", shlex.quote(str(store)))
    resources = {
        "SKILL.md": content,
        "references/workflow.md": bundle.joinpath("references/workflow.md").read_text(),
        "references/coding.json": bundle.joinpath("references/coding.json").read_text(),
        "references/ajf.schema.json": source.joinpath("ajf.schema.json").read_text(),
    }
    planned = {}
    for directory in sorted({AGENTS[agent] for agent in selected}):
        for name, text in resources.items():
            target = root / directory / "proofpress" / name
            check_path(target, root)
            if target.exists() and (not target.is_file() or (target.read_text() != text and not upgrade)):
                raise JudgmentError(f"Existing file differs; preserve or move it before setup: {target}")
            planned[target] = text
    # Preflight all conflicts before creating a store or any skill files.
    created = []
    if not dry_run:
        if not store.exists():
            initialize(store, owner)
        for target, text in planned.items():
            if target.exists() and target.read_text() != text:
                backup = store / 'skill-backups' / uuid.uuid4().hex / target.relative_to(root)
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(target.read_bytes())
                target.write_text(text)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x") as out:
                    out.write(text)
                created.append(str(target))
        manifest = store/'skills.json'
        saved = json.loads(manifest.read_text()) if manifest.exists() else {}
        saved.update({str(target):hashlib.sha256(text.encode()).hexdigest() for target,text in planned.items()})
        from .hosts import atomic_json
        atomic_json(manifest,saved)
    return {
        "ok": True, "dry_run": dry_run, "project": str(root), "workspace": str(store),
        "agents": selected, "admission": "manual", "hooks_installed": False,
        "skill_directories": sorted({str(root / AGENTS[a] / "proofpress") for a in selected}),
        "created": created,
        "next": ["Reload agent skills or start a new session in this project.",
                 "Ask the agent to use Proofpress to capture a correction; review it yourself.",
                 "Hermes requires a Git project and your own `hermes skills trust` confirmation.",
                 "Remote agents need the CLI and workspace provisioned on their own machine."],
        "boundary": "Skill entry points prepared, not live-host verification or action enforcement.",
    }
