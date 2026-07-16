# Go TUI Removal Plan

## References to Clean
- CLI: go_tui.py, main.py:174,182,211-219
- Installers: setup.sh:67-74, install-atlas-cli.ps1:48-61
- Tests: test_go_tui_launcher.py, test_go_tui_installers.py, test_tui_app_entry.py, test_permission_provenance.py:59,90, test_cross_surface_permission_conformance.py:77
- npm: packages/atlas-cli/test/commands.test.js:192-193,370-371
- Comments: atlasFetch.ts:82,127,326, atlasFetch.test.ts:103,205

## Safe Removal Sequence
1. Gate decision: confirm atlas-terminal is replacement
2. Retarget CLI entrypoint (main.py:182,211-219) to launch atlas-terminal
3. Delete go_tui.py and import at main.py:174
4. Update installer scripts (remove Go build blocks)
5. Update/delete test files
6. Delete services/atlas-tui/ directory
7. Clean comments in atlasFetch.ts
8. Update planning docs
9. Run full test suite

## What Breaks If Deleted Today
- atlas and atlas tui commands non-functional
- 3+2 test files fail
- Installer scripts fail
