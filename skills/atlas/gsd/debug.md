# GSD/L2 · debug — root cause with proof, then the fix

Use on any bug, failed verification, or unexpected behavior. The rule that
outranks urgency: **no fix before a reproduced, evidenced root cause.** A fix
without a root cause is a bet placed with the operator's time.

## Procedure

1. **Capture the symptom exactly** — the literal output/screenshot/row, not a
   paraphrase. Note what changed most recently.
2. **Reproduce or trace.** Prefer a live reproduction; when the environment
   can't drive one (no TTY, no provider), trace the data through the layers
   and say explicitly that reproduction was not possible.
3. **Hypothesize → test → narrow.** One variable at a time. Every hypothesis
   gets a check that could falsify it; record the ones that died — they are
   the map for the next session if this one runs out.
4. **Prove the cause** — point at the exact code/data (file:line, DB row,
   event) and show why it produces the symptom. "Plausible" is not "proven";
   label which one you have.
5. **Fix minimally**, add the regression test that fails without the fix,
   then run the surrounding suite.
6. **Record** — persistent bugs get a debug file
   (`.planning/debug/<slug>.md`) with symptom, killed hypotheses, root cause,
   fix commit, and residual risk, so a context reset loses nothing.

## ATLAS-native

- The audit ledger is the primary forensic source: dump the exact run's
  events/deltas from SQLite before theorizing — ATLAS keeps the evidence so
  debugging starts from records, not memory.
- Multi-layer symptoms (runtime → gateway → surface): find which layer's
  record is the first corrupted one; layers downstream of clean records are
  innocent.
- If the same failure repeats twice with no new information: stop, write the
  debug file, surface to the operator.
