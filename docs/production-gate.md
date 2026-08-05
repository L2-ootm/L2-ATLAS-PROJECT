# Isolated production gate

The production gate is a fail-fast rehearsal harness, not a deployment tool. It creates one run-specific root outside the repository, redirects every mutable ATLAS/npm path into that root, rejects default ports, and executes only the commands in its built-in catalogue. It never deletes the root. Its cleanup manifest is an allowlist for a later, separately reviewed cleanup operation.

Evidence is written atomically to `evidence/production-gate.json`. It contains gate and step IDs, labels, status, timestamps, and durations only. Command output, environment values, credentials, prompts/responses, config patches, and raw logs are intentionally excluded. A per-run secret canary makes evidence serialization fail if secret-bearing data crosses that boundary.

## Safe five-command run/resume

Run these five PowerShell commands from the repository root. Pick unused non-default ports and use the release gateway binary you intend to prove. The gate root must not exist before command 3.

```powershell
$repo = (Resolve-Path .).Path; $run = Join-Path ([System.IO.Path]::GetTempPath()) ("atlas-production-gate-" + ([guid]::NewGuid().ToString('N')))
$common = @{ Mode='source'; Repo=$repo; GateRoot=$run; AtlasHome=(Join-Path $run 'atlas-home'); Database=(Join-Path $run 'data/atlas.db'); Config=(Join-Path $run 'config/config.yaml'); NpmPrefix=(Join-Path $run 'npm-prefix'); GatewayBinary=(Join-Path $repo 'native/atlas-core-rs/target/release/atlas-gateway.exe'); ReleaseVersion='0.1.5'; Port=@(18484,15173,13001); TestCommand=@('planning','python-core','python-runtime','node-cli','rust-gateway') }
& "$repo/scripts/production/run-production-gate.ps1" @common -DryRun
& "$repo/scripts/production/run-production-gate.ps1" @common -Resume
Get-Content (Join-Path $run 'evidence/production-gate.json') | ConvertFrom-Json | Select-Object gate_id,status,started_at,finished_at
& "$repo/scripts/production/run-production-gate.ps1" @common -Resume
```

For installed mode, set `Mode='installed'` and add an absolute `InstallRoot` below `$run`. First use `-DryRun` to create the marked isolated root, install the package into that isolated prefix, and then run with `-Resume`. A resume is accepted only when the root marker exists; once execution has begun, its plan fingerprint must also match and completed hard gates are skipped.

## Meaningful-step checklist

- Confirm the gate root is new, absolute, outside the repository, and named `atlas-production-gate-<hex>`.
- Confirm ATLAS home, database, config, npm prefix, and installed prefix are explicit descendants of that root.
- Confirm all selected ports are unused, distinct, and not ATLAS defaults.
- Run the dry plan and verify the required integrity, identity, doctor, and status labels plus the selected tests.
- Treat any non-zero command as a hard stop; inspect the command directly outside evidence, fix it, then use `-Resume` with the unchanged inputs.
- Accept a run only when evidence status is `passed`; retain the cleanup manifest and never recursively delete a computed or unverified path.
