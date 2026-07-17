# @l2-ootm/atlas

Repository-linked GitHub Packages mirror of the ATLAS lifecycle launcher.

The canonical public installation uses npmjs and does not require GitHub
authentication:

```powershell
npm install --global @systemsl2/atlas
```

The launcher resolves the exact Windows x64 runtime package, verifies and
materializes an immutable release, and keeps operator state under `ATLAS_HOME`
separate from application versions. See the
[ATLAS repository](https://github.com/L2-ootm/L2-ATLAS-PROJECT) for installation,
update, rollback, security, and support documentation.
