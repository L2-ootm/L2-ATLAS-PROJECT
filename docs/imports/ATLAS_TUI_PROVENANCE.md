# ATLAS TUI Provenance

## Pinned source

ATLAS reviewed the terminal UI subtree from:

- Repository: `https://github.com/XiaomiMiMo/MiMo-Code`
- Release: `v0.1.2`
- Commit: `86d95a79bf0879bcb442ffe6b12914f6d8e68a4e`
- Path: `packages/opencode/src/cli/cmd/tui`
- Audit date: 2026-06-24

The pinned subtree contains 180 files totaling 2,630,082 bytes. Its complete
hash, size, area, classification, rationale, and intended disposition record is
in `ATLAS_TUI_SOURCE_INVENTORY.csv`.

## External-checkout-only workflow

The donor repository remains in the gitignored `_EXTERNAL_REPOS/` area or an
equivalent external read-only checkout. Raw donor source, assets, lockfiles,
generated artifacts, and repository metadata must not be committed to ATLAS.

Reviewers:

1. fetch the exact commit into an external checkout;
2. verify the checkout `HEAD`;
3. enumerate and hash the pinned subtree;
4. compare the generated inventory with the reviewed inventory;
5. classify every changed or new item before it becomes eligible for intake;
6. implement approved concepts in ATLAS-owned files;
7. run identity, dependency, network, artifact, test, and performance gates.

No broad merge, subtree import, whole-tree copy, or fork-and-rename operation is
an approved intake mechanism.

## Classification meaning

- `adopt-pattern`: a concept may be independently reimplemented. It is not
  authorization to copy the file.
- `rewrite`: the interaction or layout shape is useful, but the implementation
  is coupled to donor runtime, storage, SDK, product identity, or dependencies.
- `reject`: the item must not enter shipped ATLAS source or artifacts.

Unknown and unreviewed items fail closed as `reject`.

## Future upstream reviews

Every future upstream review must record:

- prior and candidate commit IDs;
- release/tag and review date;
- exact diff scope and changed file hashes;
- classification and rationale for every changed/new item;
- ATLAS destination or explicit rejection;
- dependency and license changes;
- source and built-artifact boundary scan results;
- tests and measured startup, memory, file-count, source-size, and artifact-size deltas;
- required attribution, license, copyright, restrictions, or notice changes.

An upstream update is not accepted merely because it is newer. It must fit the
ATLAS architecture, dependency ceilings, budgets, and one-agent/many-surfaces
contract.

## Legal and ethical posture

The reviewed repository includes an MIT license and a separate use-restrictions
document. ATLAS preserves copyright and license notices and references the
restrictions document separately. This provenance record does not provide legal
advice or claim that the interaction between those documents is resolved.
Public distribution of derivative code remains gated on explicit review or
upstream clarification.
