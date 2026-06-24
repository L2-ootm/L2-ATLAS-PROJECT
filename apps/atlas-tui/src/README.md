# ATLAS TUI source boundary

This directory owns terminal presentation and interaction only.

It must consume versioned ATLAS session, event, workspace, configuration, and
permission contracts as those contracts become available. It must not create an
independent agent runtime, provider layer, policy engine, state store, memory
authority, authentication flow, network client, updater, sharing service, or
telemetry path.

Phase 10.1 intentionally contains no backend connection. The first executable
shell is an offline rendering and lifecycle baseline.
