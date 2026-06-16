# ATLAS Auth-Store Design

> **Phase 10.0 design artifact — committed decision, no runtime code.**
> This document is the auth-store foundation that **Phase 10.1** implements
> against. It commits the on-disk layout, the single path resolver, the
> atomic-write + cross-process-lock pattern, the permission model, and the
> secrets-at-rest contract — so 10.1 builds against a reviewed spec rather than
> rediscovering the Windows/locking landmines the hard way.

**Status:** committed design (reviewable artifact)
**Mirrors:** v1.0 Phase 7 design-phase shape (clear goal, explicit "owns no
REQ-IDs", numbered TRUE-criteria, hand-off contract to the consuming phase).

## Goal

Define the ATLAS-owned auth store — a flat `~/.atlas/auth.json` file holding
provider credentials, written atomically under a cross-process lock, readable
only by the current user, with full secret values never leaking into SQLite,
audit JSONL, or any status/list command. The store is the single home for
secret material; everything else references a `provider_id` and derives status.

## Requirements ownership

**This document owns no v1 REQ-IDs; de-risks AUTH-01/02, SEC-03 (owned by 10.1).**

It de-risks **AUTH-01 / AUTH-02** (auth store create + atomic-write-under-lock)
and **SEC-03** (owner-only permissions), all of which are **owned by Phase
10.1**. Precedent: v1.0 Phase 7 was a design/enabling phase that owned no
REQ-IDs and de-risked the phases that consumed it.

## Success criteria (what must be TRUE)

1. A single resolver function `auth_store_path()` is the only path source; it
   honors an `ATLAS_HOME` env override so tests never touch the real home dir.
2. The store is a flat `~/.atlas/auth.json`, a **peer** of the existing
   `~/.atlas/atlas.db` — not a new home directory.
3. The file format carries a top-level `"version": 1` forward-migration hook and
   a `"providers"` map keyed by `provider_id`.
4. Writes are atomic-best-effort (temp + fsync + `os.replace`) **and serialized
   by a cross-process OS-handle lock** — the lock, not the rename, is the
   no-corruption guarantee (LANDMINE 1).
5. The lock is an OS-handle advisory lock (`fcntl.flock` / `msvcrt.locking` on an
   open fd) that auto-releases on process death — **not** a presence-based
   "create file, delete on exit" lock (LANDMINE 2).
6. Permissions are `0600` on POSIX and an `icacls /inheritance:r /grant:r` owner-
   only grant on Windows.
7. Full secret values are **never** returned by any status/list command, **never**
   written to SQLite, and **never** written to audit JSONL — only a computed
   `redacted_hint` is displayed.

## Layout

- **Location:** flat `~/.atlas/auth.json`, a **peer** of the existing
  `~/.atlas/atlas.db`. `~/.atlas/` is already the ATLAS home (the gateway's
  `default_db_path()` resolves there); `auth.json` is a peer, **not** a new home.
- **Single path resolver:** all auth-store path resolution goes through one
  function — `auth_store_path()` in `services/agent-runtime/atlas_runtime/`
  (e.g. `auth/store.py`). No scattered `Path.home()` calls. The resolver honors
  an `ATLAS_HOME` env override (mirroring how Hermes uses `HERMES_HOME`) so the
  test suite points at a temp dir and never mutates the real home.
- **Profile-ready in one function:** the future per-profile layout
  `~/.atlas/profiles/<name>/auth.json` is reachable as a **single-function
  change** to `auth_store_path()` — the layout is intentionally not hard-coded
  anywhere else.

## File format

A JSON object:

```json
{
  "version": 1,
  "providers": {
    "<provider_id>": {
      "auth_type": "api_key",
      "base_url": "https://...",
      "created_at": "2026-06-15T00:00:00Z",
      "last_refresh_at": "2026-06-15T00:00:00Z",
      "redacted_hint": "…ab12"
    }
  }
}
```

- Top-level `"version": 1` is the **forward-migration hook** (mirrors Hermes
  `AUTH_STORE_VERSION = 1`; Hermes already uses its version field to migrate an
  older `"systems"` format, proving the hook earns its keep).
- `"providers"` is a map keyed by `provider_id`; each entry holds `auth_type`,
  `base_url`, `created_at`, `last_refresh_at`, and a display-only
  `redacted_hint`. The raw secret material lives in this file and **only** this
  file.

## Atomic write + cross-process lock

ATLAS owns its own implementation that **mirrors the Hermes pattern but does NOT
import `foundation/atlas-hermes` internals** — so the vendored foundation stays
re-syncable against upstream and the ATLAS store carries no foundation
dependency. The save path mirrors Hermes `_save_auth_store`:

1. **Create the temp file with `os.open(O_WRONLY | O_CREAT | O_EXCL, 0600)`.**
   The `O_EXCL` + explicit `0600` mode closes the umask TOCTOU window where a
   default `0644` umask would briefly expose tokens between `open()` and a later
   `chmod()`. Temp name pattern: `auth.json.tmp.{pid}.{uuid4hex}`.
2. `write` → `flush` → **`os.fsync(fileno())`** so the temp file's bytes are on
   disk before the rename.
3. **`os.replace(tmp, auth.json)`** to swap the new file into place (resolving
   symlinks first so a symlinked `auth.json` is written in-place, not detached).
4. **`os.fsync` the parent directory fd** (POSIX) so the rename itself is durable.
5. Best-effort `chmod(0600)` after replace.

The whole save (and every load) runs **inside a cross-process lock** held on a
**sidecar lock file** (a sibling such as `auth.lock`, kept out of any `*.json`
glob), acquired with an ~`15s` timeout that mirrors Hermes
`AUTH_LOCK_TIMEOUT_SECONDS = 15.0`, polled until a `time.monotonic()` deadline,
raising `TimeoutError` on expiry.

**Windows msvcrt quirk — must be replicated:** `msvcrt.locking` requires the
lock file to have **≥1 byte** and the file pointer at **position 0**. The ATLAS
mirror must write a single byte if the lock file is empty and `seek(0)` before
lock/unlock, exactly as Hermes does — otherwise Windows locking silently no-ops
and provides no serialization.

**Corruption resilience:** on a `json.loads` failure during load, copy the file
to `auth.json.corrupt` and return an empty store rather than crashing
(`.corrupt`-preservation recovery). This makes a torn write recoverable, not
silently lost.

### LANDMINE 1 — `os.replace` is NOT guaranteed atomic on Windows

`os.replace` maps to Win32 `MoveFileEx(MOVEFILE_REPLACE_EXISTING)`, which is
**not guaranteed to be atomic** when the target already exists — under certain
conditions it can silently fall back to a **non-atomic** `CopyFile`. Therefore:

- The phrasing "atomic write via temp + `os.replace`" is **POSIX-true,
  Windows-best-effort**. This design does **not** claim hard atomicity on
  Windows.
- The **cross-process lock — not the rename — is the no-corruption guarantee**
  on Windows. The lock serializes writers so two `os.replace` calls never race;
  fsync-before-replace means the temp file is fully on disk; and the `.corrupt`-
  preservation fallback makes a torn write recoverable. AUTH-02's
  "concurrent writers never corrupt or silently lose data" property is delivered
  by the **lock**, backed by fsync and `.corrupt` recovery — explicitly not by
  `os.replace`.
- Do **not** add the `atomicwrites` PyPI dependency to "fix" this — it is in
  maintenance mode and violates D-022 dependency discipline; mirroring Hermes
  (zero new deps) is the correct posture.

### LANDMINE 2 — the lock is an OS-handle advisory lock, NOT a presence lock

The cross-process lock **must** be an OS-handle advisory lock —
`fcntl.flock(LOCK_EX)` on POSIX / `msvcrt.locking(LK_NBLCK, 1)` on Windows, held
on an **open file descriptor**. Such locks are released automatically by the OS
when the holding process/handle dies, so a crash mid-write does **not** leave a
permanently-held lock.

It must **not** be a **presence-based** lock (the naive "create a lock file,
delete it on exit" scheme). A presence-based lock **deadlocks after a crash**:
the file is left on disk and every subsequent writer waits forever. 10.1 must
**not "simplify"** the OS-handle lock into a presence check — the auto-release-
on-death property is load-bearing for crash-safety.

## Permissions

Created **current-user-only**:

- **POSIX:** `os.chmod(path, S_IRUSR | S_IWUSR)` = `0o600`. The temp file is
  already created `0600` via `O_EXCL` (above) to avoid the umask window.
- **Windows:** `os.chmod` only toggles the read-only bit and does **not** set
  ACLs, so SEC-03 requires `icacls`. The exact command shape:

  ```
  icacls "<path>\auth.json" /inheritance:r /grant:r "<user>:(F)" /Q
  ```

  - `/inheritance:r` strips all inherited ACEs (otherwise `Users` /
    `Authenticated Users` inherit read access).
  - `/grant:r "<user>:(F)"` replaces explicit grants with current-user **Full**
    only.
  - Invoke via `subprocess` with the path passed as a **list arg** (no shell-
    string interpolation) to avoid command injection.

  **Open question deferred to 10.1:** robust current-user identity resolution —
  `%USERNAME%` vs SID vs `DOMAIN\user`. SID is more robust for domain accounts;
  the exact identity call is left to 10.1. `%USERNAME%` is acceptable for this
  draft but is flagged as not domain-safe.

## Secrets at rest

- **File-store-first (v1.1).** Secrets live in the user-only-perms file. OS
  keychain integration is **deferred to v1.2 (AUTHX-01)**.
- **`redacted_hint`** (e.g. last 4 chars) is computed and stored for display.
- **Full secret values are NEVER returned by any status/list command, NEVER
  written to SQLite, and NEVER written to audit JSONL.**
- The redaction primitive is the **existing** `SECRET_PATTERNS` set in
  `packages/atlas-core/atlas_core/schemas/core.py` (token / api_key / secret /
  password / bearer regexes). **Do not invent a new regex set** — `SECRET_PATTERNS`
  is the single source of truth for SEC-01 and is already tested.

## Credential boundary (links to the registry, Area 3)

Credentials live **only** in the file store. The SQLite registry references a
`provider_id` and **derives** `auth_status` (e.g. `available` / `auth_present` /
`needs_api_key` / `needs_login` / `offline` / `rate_limited`) at discovery time
from the file store — it **never holds secret material**. This is the hard
boundary that keeps secrets out of the database and the gateway read path.

## Hand-off contract to Phase 10.1

10.1 implements this design and must, at minimum:

- Provide `auth_store_path()` honoring `ATLAS_HOME`; never call `Path.home()`
  elsewhere.
- Implement the atomic-save + OS-handle-lock + `.corrupt` recovery, including the
  Windows `msvcrt` 1-byte + `seek(0)` quirk.
- Apply `0600` (POSIX) / `icacls /inheritance:r /grant:r` (Windows) and resolve
  the Windows identity question.
- Reuse `core.py SECRET_PATTERNS` for all redaction; expose only `redacted_hint`.
- Carry the test contract: roundtrip, concurrent-lock, malformed-file-safe,
  redaction, Windows-path, icacls-perms, and the `~/.codex` byte-identity
  invariant (SEC-02).
