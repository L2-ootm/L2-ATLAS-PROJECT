# ATLAS v1.0 — Visual CLI Manual

**Purpose:** show the operator how to visually inspect and use the ATLAS CLI created for v1.0.

**Current project state:** v1.0 has been UAT-approved and archived. The next milestone is not active yet. The CLI remains the real write path behind the Rust gateway and the web cockpit.

**Important distinction:**

- The **visual product UI** is the browser cockpit: missions, runs, audit stream, wiki, models.
- The **CLI** is a terminal interface built with Typer/Rich. It is “visual” in the terminal: structured command panels, help screens, status output, and IDs.
- The native desktop shell with terminal panes is **v1.1 / Phase 10**, not v1.0.

---

## 1. Open the project in a terminal

Use **Windows Terminal** or **Git Bash**.

```bash
cd <USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT
```

If the `atlas` command is not installed in your shell, use the module form below. This is verified in the current repo:

```bash
python -m atlas_runtime.cli.main --help
```

Expected visual output: a Rich/Typer command panel with these top-level commands:

```txt
mission
wiki
foundation
models
channels
```

Optional install path for the shorter `atlas` command:

```bash
pip install -e packages/atlas-core
pip install -e services/agent-runtime
pip install -e services/wiki-runtime
```

After that, try:

```bash
atlas --help
```

If `atlas` still does not resolve, keep using:

```bash
python -m atlas_runtime.cli.main ...
```

---

## 2. Visually inspect the CLI surface

Run these commands one by one. You are not changing data; these only show the command structure.

```bash
python -m atlas_runtime.cli.main --help
python -m atlas_runtime.cli.main mission --help
python -m atlas_runtime.cli.main wiki --help
python -m atlas_runtime.cli.main models --help
python -m atlas_runtime.cli.main foundation --help
python -m atlas_runtime.cli.main channels --help
```

What you should see:

- boxed terminal help panels;
- command names aligned in rows;
- option descriptions;
- no browser required.

This is the fastest way to **see the CLI that was created**.

---

## 3. Check the foundation status

This confirms the vendored ATLAS/Hermes foundation is present and wired.

```bash
python -m atlas_runtime.cli.main foundation status
```

Expected current output shape:

```txt
vendor:               <USER_HOME>\Desktop\Projects\L2-ATLAS-PROJECT\foundation\atlas-hermes
pinned upstream SHA:  e8b9369a9d2df36139a5055cae3ed3c15691e03e (NousResearch/hermes-agent, MIT)
installed:            yes
audit plugin bundled: yes
divergences logged:   6
```

If this works, the foundation layer is visible from the CLI.

---

## 4. Check the model registry

```bash
python -m atlas_runtime.cli.main models list
```

Expected current output includes seeded model rows, for example:

```txt
claude-fable-5 (anthropic)
claude-sonnet-4-6 (anthropic)
gemini-2.5-pro (google)
```

This is read-only and safe.

---

## 5. Check channel configuration

```bash
python -m atlas_runtime.cli.main channels status
```

Expected current output shape:

```txt
foundation home: <USER_HOME>\AppData\Local\hermes
no channels configured (gateway.platforms is empty)
enable one: atlas-agent config set gateway.platforms.<name>.enabled true
```

This command never prints credential values. It only reports whether credentials exist.

---

## 6. See and test the mission CLI

### 6.1 Show mission commands

```bash
python -m atlas_runtime.cli.main mission --help
```

Available commands:

```txt
create  Create a Mission and print its ID.
run     Start a Run for the given mission and print the run ID.
cancel  Cancel all active runs for the given mission.
status  Print the status of the given mission.
```

### 6.2 Create a demo mission

This writes one mission to `~/.atlas/atlas.db`.

```bash
MISSION_ID=$(python -m atlas_runtime.cli.main mission create \
  --title "Visual CLI Demo" \
  --intent "See the ATLAS v1.0 CLI from the terminal")

echo "$MISSION_ID"
```

Expected: a UUID-like mission ID.

### 6.3 Check mission status

```bash
python -m atlas_runtime.cli.main mission status "$MISSION_ID"
```

Expected:

```txt
pending
```

### 6.4 Start a run

```bash
RUN_ID=$(python -m atlas_runtime.cli.main mission run "$MISSION_ID")
echo "$RUN_ID"
```

Expected: a UUID-like run ID.

### 6.5 Cancel active run(s)

```bash
python -m atlas_runtime.cli.main mission cancel "$MISSION_ID"
```

Expected:

```txt
cancelled
```

This is the same write path the Rust gateway uses for cockpit mission actions.

---

## 7. See and test the wiki CLI

### 7.1 Show wiki commands

```bash
python -m atlas_runtime.cli.main wiki --help
```

Available commands:

```txt
ingest
update
search
semantic
lint
```

### 7.2 Create/update a demo wiki page

```bash
python -m atlas_runtime.cli.main wiki update visual-cli-demo \
  --title "Visual CLI Demo" \
  --body "This page was created from the ATLAS v1.0 CLI manual."
```

Expected:

```txt
visual-cli-demo
```

### 7.3 Search for it

```bash
python -m atlas_runtime.cli.main wiki search "visual cli" --limit 5
```

Expected: a row containing `visual-cli-demo`.

### 7.4 Lint the wiki

```bash
python -m atlas_runtime.cli.main wiki lint
```

Expected:

```txt
no lint findings
```

or a list of explicit findings if the dev wiki has issues.

---

## 8. Open the visual cockpit next to the CLI

If your goal is to **see the product visually**, run the browser cockpit. The CLI will still be active underneath.

### Terminal A — start gateway

```bash
cd <USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT
./native/atlas-core-rs/target/release/atlas-gateway.exe
```

If the binary is stale or missing, rebuild and run:

```bash
cd <USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT/native/atlas-core-rs
cargo build --release -p atlas-gateway
./target/release/atlas-gateway.exe
```

Health check from another terminal:

```bash
curl http://127.0.0.1:8484/health
```

### Terminal B — start cockpit

```bash
cd <USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT/services/web-ui
npm install
npm run dev
```

Open:

```txt
http://localhost:5173
```

What to inspect visually:

1. Mission list.
2. Create mission modal.
3. Mission detail page.
4. Run launch/cancel flow.
5. Live audit stream.
6. Wiki search/browser.
7. Read-only model registry.

---

## 9. Recommended first 10-minute walkthrough

Run this exact sequence:

```bash
cd <USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT
python -m atlas_runtime.cli.main --help
python -m atlas_runtime.cli.main foundation status
python -m atlas_runtime.cli.main models list
python -m atlas_runtime.cli.main mission --help
```

Then create one CLI mission:

```bash
MISSION_ID=$(python -m atlas_runtime.cli.main mission create \
  --title "Operator Visual CLI Walkthrough" \
  --intent "Verify what the ATLAS CLI can do visually in terminal")
python -m atlas_runtime.cli.main mission status "$MISSION_ID"
RUN_ID=$(python -m atlas_runtime.cli.main mission run "$MISSION_ID")
echo "mission=$MISSION_ID run=$RUN_ID"
python -m atlas_runtime.cli.main mission cancel "$MISSION_ID"
```

Then open the browser cockpit and confirm the mission/run appeared there.

---

## 10. What exists in v1.0 vs what does not

### Exists now

- `mission create/run/cancel/status`
- `wiki ingest/update/search/semantic/lint`
- `models refresh/list`
- `foundation status/smoke`
- `channels status`
- Rust gateway reading SQLite and dispatching writes through the CLI
- Web cockpit showing missions, runs, audit stream, wiki, and models

### Not v1.0

- Native Tauri desktop shell
- built-in terminal pane inside the app
- `atlas db init`
- configurable CLI DB path
- visual command palette / global hotkey
- keychain-backed model/provider mutation UI

Those are v1.1 / Phase 10+ concerns.

---

## 11. If something fails

### `No module named atlas_runtime`

Run editable installs from the repo root:

```bash
pip install -e packages/atlas-core
pip install -e services/agent-runtime
pip install -e services/wiki-runtime
```

### `no such table: missions`

The DB schema was not bootstrapped. Apply migrations once:

```bash
python - <<'PY'
import pathlib, sqlite3
root = pathlib.Path('.').resolve()
db = pathlib.Path.home() / '.atlas' / 'atlas.db'
db.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(str(db))
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA foreign_keys = ON')
for sql in sorted((root / 'infra' / 'migrations').glob('*.sql')):
    conn.executescript(sql.read_text(encoding='utf-8'))
    print('applied', sql.name)
conn.commit(); conn.close()
PY
```

### Cockpit says gateway offline

Start/rebuild the gateway:

```bash
cd <USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT/native/atlas-core-rs
cargo build --release -p atlas-gateway
./target/release/atlas-gateway.exe
```

Then verify:

```bash
curl http://127.0.0.1:8484/health
```

---

## Bottom line

To **see the CLI visually**, start here:

```bash
cd <USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT
python -m atlas_runtime.cli.main --help
```

To **see the product visually**, start the gateway + web cockpit and open:

```txt
http://localhost:5173
```
