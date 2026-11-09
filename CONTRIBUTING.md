# Contribute to Proofpress Judgment

Start with a small, focused issue or pull request. Bug fixes, integration reports,
clearer documentation and reproducible evaluations are welcome.

## Develop locally

Requires Python 3.11+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python examples/walkthrough.py --synthetic-review-fixture
```

The walkthrough uses a disposable synthetic owner. Keep local `.judgment/` stores,
credentials and private agent history out of commits and issues. Public examples
must use synthetic data or material you have permission to publish.

## Open a pull request

Fork the repository, create a branch and explain the concrete behavior change.
Include the checks you ran and any limits. Keep unrelated edits separate. Docs-only
changes need link/command verification rather than new tests that repeat the text.

`main` requires a pull request, one approving review, resolved review threads and
passing `test (3.11)` / `test (3.13)` checks from GitHub Actions. New commits dismiss
stale approvals, and the latest push needs independent approval. External fork
workflows require maintainer approval before they run. Richard retains the same
explicit owner bypass used in the original Proofpress repository; this does not
grant contributors direct write access. Merges use squash and remove the branch.

## Preserve judgment boundaries

Capture and revision create candidates, not approval. Keep immutable revisions,
exact-digest review, conservative conditions and stale-binding invalidation intact.
Use clearly labeled synthetic owner actions in tests. Agents must not impersonate
a human reviewer or approve their own real records. Preserve upstream licenses and
attribution when reusing code.

Live host/provider checks are opt-in and may incur model usage. Describe the exact
host, version and covered tool route; a mocked event is not live-host evidence.
Do not include private transcripts or keys in verification receipts.

## Report a security issue

Use [private vulnerability reporting](https://github.com/continuara-lab/proofpress-judgment/security/advisories/new).
Do not post working credentials or exploit details in a public issue.
[Security boundaries](SECURITY.md)

## Work together

Be respectful, focus feedback on the change and avoid harassment or disclosure of
other people's private information. Maintainers may close abusive or unrelated
submissions. Contributions are provided under the repository's Apache-2.0 license;
retain copyright notices and the rights needed to contribute your changes.
