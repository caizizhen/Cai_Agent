# ECC-N04-D03: Ingest provenance, signature, and trust levels (draft)

> English companion. Canonical Chinese: [ECC_04C_INGEST_PROVENANCE_TRUST.zh-CN.md](ECC_04C_INGEST_PROVENANCE_TRUST.zh-CN.md).

## Summary

This draft sits on top of **`ECC-N04-D01`** (`ecc_asset_registry_v1` metadata) and **`ECC-N04-D02`** (ingest sanitizer / dangerous hook isolation). It defines **provenance**, **integrity**, **signature**, and **trust level** semantics and how they **combine with sanitizer decisions** into a conservative gate for future import/install flows.

## Non-goals (this tranche)

- No real **GPG / Sigstore / TUF** verification pipeline; `signature.verified` remains a manual or external CI signal.
- No auto-execution of untrusted hooks/scripts; execution stays behind **`ECC-N04-D02`** `deny-exec` and `hook_runtime` policies.

## Machine-readable draft

See `docs/schema/ecc_ingest_provenance_trust_v1.snapshot.json` (`schema_version`: `ecc_ingest_provenance_trust_v1`).

## Acceptance

- Bilingual policy docs + snapshot JSON checked into `docs/schema/`.
- Registry snapshot `boundaries.provenance_policy_included` set to `true`.
- `ROADMAP_EXECUTION.zh-CN.md` §10, developer todos, changelog, and schema README entries updated consistently.
