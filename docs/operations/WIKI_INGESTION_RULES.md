# Wiki Ingestion Rules

Rules for `wiki/raw/` and the `atlas wiki ingest` command (Phase 6 runtime,
D-019). These rules govern what may be ingested into the ATLAS wiki store.

## Ingestion Rules

1. **No secrets.** Never ingest files containing API keys, passwords, tokens,
   session data, or credentials of any kind — even in encrypted or hashed
   form.

2. **No raw personal data.** Chat logs, email exports, personal identifiers,
   or private conversation exports must not be ingested without explicit
   operator review and redaction.

3. **Provenance required.** Every ingested source must have a matching `Source`
   row in the SQLite registry (auto-created by `atlas wiki ingest`) with a
   clear `kind`, `uri`, and `sha256`. Orphaned raw files without a registry
   entry should be deleted.

4. **Compiled knowledge belongs in `wiki/`**, not `wiki/raw/`. Entities go in
   `wiki/entities/`, concepts in `wiki/concepts/`, comparisons in
   `wiki/comparisons/`. `wiki/raw/` is a staging area only — treat it as
   transient.

5. **Generated and runtime artifacts do not belong here.** Coverage reports,
   log exports, binary snapshots, and test fixtures belong in `artifacts/`
   (gitignored) or are referenced by path from wiki entries.

6. **Ingest only intentional, operator-reviewed content.** Automated
   bulk-ingestion from external sources requires a documented intake reason
   and post-ingest lint pass (`atlas wiki lint`).

## wiki/raw/ Policy

The `wiki/raw/` directory is preserved for sources that are safe, intentional,
and small enough to track in git. It should remain nearly empty in practice.
If a raw source grows large or is sensitive, use an external reference in the
Source registry (kind `url` or `file_ref`) rather than storing the content.

## Reference

- Phase 6 PLAN: `services/atlas-wiki/`
- SQLite schema: `infra/migrations/0002_provenance.sql`
- CLI: `atlas wiki ingest <path>`, `atlas wiki lint`
