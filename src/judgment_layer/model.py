"""Portable content, intentionally separate from admission authority."""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker


class JudgmentError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
        raise JudgmentError("Timestamp must be RFC3339 with a timezone")
    try:
        result = datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
    except ValueError as exc:
        raise JudgmentError("Invalid timestamp") from exc
    if result.tzinfo is None:
        raise JudgmentError("Timestamp must include a timezone")
    return result


SCHEMA = json.loads(files("judgment_layer").joinpath("ajf.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def validate(record):
    try:
        canonical(record)
    except (TypeError, ValueError) as exc:
        raise JudgmentError("Record must be finite JSON") from exc
    errors = sorted(VALIDATOR.iter_errors(record), key=lambda e: str(list(e.path)))
    if errors:
        raise JudgmentError("AJF: " + errors[0].message)
    app = record["applicability"]
    instant(record["provenance"]["recorded_at"])
    for key in ("valid_from", "valid_until"):
        if key in app:
            instant(app[key])
    if "valid_from" in app and "valid_until" in app:
        if instant(app["valid_from"]) >= instant(app["valid_until"]):
            raise JudgmentError("valid_until must follow valid_from")
    fields = [c["field"] for c in app["when"]]
    if len(fields) != len(set(fields)):
        raise JudgmentError("A condition field may appear only once")
    revises = [x for x in record["links"] if x["relation"] == "revises"]
    if record["version"] == 1 and revises:
        raise JudgmentError("Version 1 cannot revise another record")
    if record["version"] > 1 and (len(revises) != 1 or revises[0]["id"] != record["id"]
                                    or revises[0]["version"] != record["version"] - 1):
        raise JudgmentError("Revision must link the exact preceding version of this judgment")
    for link in record["links"]:
        if link["relation"] == "depends_on" and link["id"] == record["id"]:
            raise JudgmentError("A judgment cannot depend on itself")
    return record


def validate_facts(facts):
    if not isinstance(facts, dict):
        raise JudgmentError("Facts must be a JSON object")
    for key, value in facts.items():
        if not isinstance(key, str) or (value is not None and type(value) not in (str, int, float, bool)):
            raise JudgmentError("Facts must map field names to JSON scalar values")
        if isinstance(value, float) and not math.isfinite(value):
            raise JudgmentError("Facts must be finite")


def applies(record, scope, facts, at=None):
    app = record["applicability"]
    if scope != app["scope"]:
        return "scope_mismatch"
    at = instant(at or now())
    if "valid_from" in app and at < instant(app["valid_from"]):
        return "not_yet_valid"
    if "valid_until" in app and at >= instant(app["valid_until"]):
        return "expired"
    for cond in app["when"]:
        if cond["field"] not in facts:
            return "missing_fact:" + cond["field"]
        actual, expected = facts[cond["field"]], cond["equals"]
        # Do not let Python's True == 1 turn a missing semantic distinction into a match.
        if canonical(actual) != canonical(expected):
            return "condition_mismatch:" + cond["field"]
    return None


def render(record):
    # JSON-quoted strings are valid YAML scalars; there is no second editable source.
    header = "\n".join(f"{key}: {json.dumps(record[key], ensure_ascii=False)}"
                       for key in ("name", "version", "description"))
    return "---\n" + header + "\n---\n\n```json\n" + json.dumps(record, indent=2, ensure_ascii=False) + "\n```\n"
