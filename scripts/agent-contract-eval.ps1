$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$runtime = Join-Path $repo "services\agent-runtime"

Push-Location $runtime
try {
    & $python -m pytest `
        tests/test_agent_contract_schema.py `
        tests/test_prompt_compiler.py `
        tests/test_tool_catalog.py `
        tests/test_tool_capability_conformance.py `
        tests/test_brain_service.py `
        tests/test_context_retrieval_contract.py `
        tests/test_agent_contract_service.py `
        tests/test_compaction_resume_contract.py `
        tests/evals/test_agent_contract_evals.py -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python -c @'
import json
from pathlib import Path
from atlas_runtime.evals.agent_contract import evaluate_dataset
from atlas_runtime.tool_catalog import build_shipped_catalog

fixture = Path("tests/evals/fixtures/agent_contract_scenarios.json")
report = evaluate_dataset(json.loads(fixture.read_text(encoding="utf-8")))
catalog = build_shipped_catalog()
print(json.dumps({
    "catalog_sha256": catalog.catalog_sha256,
    "critical_pass_rate": report.critical_pass_rate,
    "retrieval_abstention": report.retrieval_abstention,
    "retrieval_precision": report.retrieval_precision,
    "retrieval_recall": report.retrieval_recall,
    "scenario_count": report.scenario_count,
    "secret_leaks": report.secret_leaks,
    "unapproved_side_effects": report.unapproved_side_effects,
    "completion_honesty": report.completion_honesty,
    "promoted": report.promoted,
}, sort_keys=True))
raise SystemExit(0 if report.promoted else 1)
'@
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

$scanTargets = @(
    (Join-Path $repo "docs\contracts\ATLAS_TOOL_CAPABILITIES.json"),
    (Join-Path $repo "services\agent-runtime\atlas_runtime\prompts\atlas_core.md")
)
$secretPattern = 'sk-[A-Za-z0-9]{12,}|Bearer\s+[A-Za-z0-9._-]{12,}'
$matches = Select-String -Path $scanTargets -Pattern $secretPattern -AllMatches
if ($matches) {
    $matches | ForEach-Object { Write-Error "Secret canary detected: $($_.Path):$($_.LineNumber)" }
    exit 1
}

Write-Host "ATLAS agent contract promotion gate: PASSED"
