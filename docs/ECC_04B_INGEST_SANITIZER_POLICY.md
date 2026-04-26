# ECC-N04-D02 Ingest Sanitizer Policy (Draft)

Chinese canonical source: [`ECC_04B_INGEST_SANITIZER_POLICY.zh-CN.md`](ECC_04B_INGEST_SANITIZER_POLICY.zh-CN.md).

This draft defines the minimum safety gate for external asset ingest:

- default `deny-exec` for untrusted external assets
- metadata-first validation (`source/license/signature/version/trust`)
- workspace-only script resolution
- dangerous command pattern blocking and review routing

The policy is intentionally pre-implementation and review-oriented. It does not enable automatic execution of external hooks/scripts in this cycle.

Follow-up **`ECC-N04-D03`** (provenance / signature / trust gate that combines with sanitizer output): see [`ECC_04C_INGEST_PROVENANCE_TRUST.md`](ECC_04C_INGEST_PROVENANCE_TRUST.md) and `docs/schema/ecc_ingest_provenance_trust_v1.snapshot.json`.
