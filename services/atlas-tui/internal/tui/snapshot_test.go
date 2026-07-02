package tui

import (
	"os"
	"strings"
	"testing"

	"atlas-tui/internal/client"
)

// TestSnapshotViews writes plain-text renders of the idle, active, and
// onboarding states when ATLAS_TUI_SNAPSHOT is set — an eyeball artifact for
// UAT, not an assertion. Always-on assertions: every state fits its width.
func TestSnapshotViews(t *testing.T) {
	m := chatReadyModel(100, 30)
	idle := m.View()

	active := chatReadyModel(100, 30)
	active.items = []transcriptItem{
		{kind: itemUser, text: "explain the provider mesh in two paragraphs"},
		{kind: itemTool, label: "wiki_search", text: "provider mesh", status: "done", callID: "c1"},
		{kind: itemAssistant, text: "The provider mesh routes every run through one of four auth modes.\n\n- **api_key** direct keys\n- **oauth_import** Codex/ChatGPT\n\n```\natlas provider status\n```"},
		{kind: itemRule, label: "run succeeded"},
	}
	active.layout()
	activeView := active.View()

	onboarding := chatReadyModel(100, 30)
	onboarding.status.MockMode = true
	onboarding.status.CredentialsPresent = false
	onboarding.modes = []client.ProviderMode{
		{Mode: "api_key", Label: "API key", Active: true},
		{Mode: "oauth_import", Label: "Codex OAuth", Available: true},
		{Mode: "claude_code", Label: "Claude Code", Available: true},
	}
	onboardingView := onboarding.View()

	for name, view := range map[string]string{
		"idle": idle, "active": activeView, "onboarding": onboardingView,
	} {
		assertLinesFit(t, plain(view), 100)
		if os.Getenv("ATLAS_TUI_SNAPSHOT") != "" {
			path := "../../snapshot-" + name + ".txt"
			if err := os.WriteFile(path, []byte(view), 0o644); err != nil {
				t.Fatal(err)
			}
		}
	}
	_ = strings.TrimSpace("")
}
