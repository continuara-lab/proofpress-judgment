"""Offline CLI integration walkthrough. Only synthetic owner-review fixtures."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-review-fixture", action="store_true", required=True)
    parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="judgment-walkthrough-") as temp:
        workspace = Path(temp) / "store"

        def cli(*args, expected=0):
            result = subprocess.run([sys.executable, "-m", "judgment_layer.cli", "--workspace", str(workspace), *args, "--json"],
                                    capture_output=True, text=True)
            if result.returncode != expected:
                raise RuntimeError(f"CLI {args[0]} failed: {result.stderr} {result.stdout}")
            return json.loads(result.stdout)

        def context(facts="coding-facts.json"):
            return cli("context", "--scope", "coding/generated-files", "--facts", str(root / "examples" / facts),
                       "--actor", "agent:session-b", "--purpose", "Synthetic lifecycle test")

        def simulated_owner(item, action):
            command = ["withdraw"] if action == "withdraw" else ["review"]
            command += [item["id"], "--version", str(item["version"]), "--digest", item["digest"],
                        "--reason", "Explicit synthetic owner-review fixture, not a real approval", "--confirm"]
            if action != "withdraw":
                command.append("--admit")
            return cli(*command)

        cli("init", "--owner", "human:synthetic-review-fixture")
        first = cli("capture", "--from", str(root / "examples/coding.json"))
        assert context()["judgments"] == []
        simulated_owner(first, "admit")
        initial = context()
        assert len(initial["judgments"]) == 1
        old_receipt = initial["receipt"]["receipt_id"]
        cli("check", "--receipt", old_receipt, "--facts", str(root / "examples/coding-facts.json"))
        assert context("coding-not-applicable.json")["judgments"] == []
        second = cli("revise", first["id"], "--from", str(root / "examples/coding-v2.json"),
                     "--base-digest", first["digest"], "--reason", "Narrow the synthetic conditions")
        assert context()["judgments"][0]["version"] == 1
        simulated_owner(second, "admit")
        assert context()["judgments"][0]["version"] == 2
        stale = cli("check", "--receipt", old_receipt, "--facts", str(root / "examples/coding-facts.json"), expected=3)
        current_receipt = context()["receipt"]["receipt_id"]
        simulated_owner(second, "withdraw")
        withdrawn = cli("check", "--receipt", current_receipt, "--facts", str(root / "examples/coding-facts.json"), expected=3)
        assert context()["judgments"] == []
        trace = cli("import-trace", "--session", str(root / "examples/trace-session.json"), "--event", "evt_001",
                    "--template", str(root / "examples/trace-template.json"), "--recorded-by", "agent:importer")
        assert trace["state"] == "proposed"
        assert context()["judgments"] == []
        report = {"ok": True, "scenario": "capture → manual fixture review → applicable reuse → revise → supersede → withdraw",
                  "manual_fixture_only": True, "stale_after_revision": stale["reasons"],
                  "stale_after_withdrawal": withdrawn["reasons"], "trace_acceptance_imported_as": trace["state"],
                  "audit": cli("audit"), "production_or_efficacy_claim": False}
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
