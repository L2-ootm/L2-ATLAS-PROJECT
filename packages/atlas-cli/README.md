# @l2/atlas

The official installer and lifecycle launcher for the ATLAS AI operator cockpit.

```powershell
npm install --global @l2/atlas
atlas doctor
atlas up
```

The npm command installs the launcher and the complete verified release for the
current platform. Normal `atlas` commands are delegated to the active release.

```powershell
atlas update
atlas rollback
atlas versions
atlas uninstall
```

Application releases are immutable and live in the OS application-data directory.
Operator state lives separately under `ATLAS_HOME` (default `~/.atlas`), so updates
and rollbacks preserve the database, configuration, credentials, wiki, logs, and
user-created modules.

ATLAS is currently a research preview. Do not use it with sensitive data until the
public release hardening checklist is complete.
