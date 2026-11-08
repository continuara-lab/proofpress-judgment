# Proofpress provenance source fork

Source: https://github.com/Thru-Echoes/TRACE
Base commit: d18a0bd1bf36eb625836fbbab78ae4bbd78c0db9
Source author: Oliver Muellerklein. Apache-2.0; original LICENSE and NOTICE retained.

This is a checked-in source fork inside the local Proofpress Playground repo,
not a network service or separately launched TRACE product. No remote fork has
been published. Runtime changes are made here and reviewed with this demo.

Initial modifications:
- Development distribution version has a Proofpress local suffix.
- Package description identifies the local provenance core.
- Trailing whitespace in upstream README/CHANGELOG is normalized.
- Upstream CLI entry points are removed; the product entry remains ./demo.
- The original Python namespace and 0.5.1 wire format are retained internally
  for source compatibility. They do not define Proofpress's user-facing model.

Proofpress's provenance.py presents sessions, judgments and corrections using
this fork's implementations. Proofpress owns future-use review, applicability,
revision, withdrawal and receipts. Recording or accepting a historical decision
never admits a reusable judgment. Learning extraction and automatic recall are
not enabled; no second channel may inject unadmitted advice.

Preserve the upstream source, tests and attribution. Incorporate upstream fixes
explicitly rather than silently updating a Git dependency during installation.
