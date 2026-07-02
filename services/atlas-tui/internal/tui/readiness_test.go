package tui

import (
	"strings"
	"testing"

	"atlas-tui/internal/client"
)

func TestExecutionReadinessStates(t *testing.T) {
	remediation := "configure an API key or select Claude Code"
	tests := []struct {
		name      string
		status    client.ProviderStatus
		allowMock bool
		kind      readinessKind
		canRun    bool
	}{
		{
			name:   "live",
			status: client.ProviderStatus{Provider: "anthropic", Model: "claude", MockMode: false},
			kind:   readinessLive,
			canRun: true,
		},
		{
			name:   "missing provider projection",
			status: client.ProviderStatus{},
			kind:   readinessUnconfigured,
		},
		{
			name: "unconfigured",
			status: client.ProviderStatus{
				Provider: "openrouter", MockMode: true, Remediation: &remediation,
			},
			kind: readinessUnconfigured,
		},
		{
			name: "degraded",
			status: client.ProviderStatus{
				Provider: "openrouter", MockMode: true, CredentialsPresent: true,
				Remediation: &remediation,
			},
			kind: readinessDegraded,
		},
		{
			name:      "explicit mock",
			status:    client.ProviderStatus{Provider: "mock", MockMode: true},
			allowMock: true,
			kind:      readinessMock,
			canRun:    true,
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := readinessFor(tc.status, tc.allowMock)
			if got.Kind != tc.kind || got.CanRun != tc.canRun {
				t.Fatalf("readiness = %+v, want kind=%q canRun=%v", got, tc.kind, tc.canRun)
			}
		})
	}
}

func TestSubmitBlocksImplicitMockAndPreservesDraft(t *testing.T) {
	m := readyModel(120, 36)
	m.status.MockMode = true
	m.status.CredentialsPresent = false
	remediation := "select an available provider"
	m.status.Remediation = &remediation
	m.focus = focusComposer
	m.composer.Focus()
	m.composer.SetValue("analyse the codebase")

	updated, cmd := m.submitComposer()
	got := updated.(model)
	if cmd == nil {
		t.Fatal("blocked submit must load provider settings")
	}
	if got.composer.Value() != "analyse the codebase" {
		t.Fatalf("draft was lost: %q", got.composer.Value())
	}
	if got.focus != focusSettings || !got.settingsLoading {
		t.Fatalf("blocked submit did not open provider settings: focus=%v loading=%v", got.focus, got.settingsLoading)
	}
	if !strings.Contains(got.errMsg, "LIVE PROVIDER REQUIRED") {
		t.Fatalf("missing honest readiness notice: %q", got.errMsg)
	}
}
