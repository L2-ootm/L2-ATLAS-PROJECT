package tui

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"atlas-tui/internal/client"
)

func chatReadyModel(width, height int) model {
	m := New(nil, "http://127.0.0.1:8484")
	m.phase = phaseReady
	m.width, m.height = width, height
	m.status.Provider = "anthropic"
	m.status.Model = "claude-sonnet-4"
	m.status.AuthMode = "claude_code"
	m.status.MockMode = false
	m.surface.ID = "surface-chat"
	m.surface.State = "active"
	m.surface.PermissionMode = "ask"
	m.surface.Workspace.Kind = "project"
	m.surface.Workspace.Root = `C:\atlas`
	m.layout()
	return m
}

func TestChatFirstLaunchFocusesComposer(t *testing.T) {
	m := New(nil, "http://127.0.0.1:8484")
	if m.focus != focusComposer || !m.composer.Focused() {
		t.Fatalf("launch focus = %v focused=%v, want composer", m.focus, m.composer.Focused())
	}
}

func TestIdleViewIsChatFirstNotDashboardFirst(t *testing.T) {
	view := plain(chatReadyModel(140, 40).View())
	for _, forbidden := range []string{"provider modes", "missions", "permissions (", "run stream"} {
		if strings.Contains(view, forbidden) {
			t.Fatalf("idle view contains dashboard chrome %q:\n%s", forbidden, view)
		}
	}
	for _, required := range []string{"L2 // ATLAS", "MESSAGE ATLAS", "claude-sonnet-4", "/ commands"} {
		if !strings.Contains(view, required) {
			t.Fatalf("idle view missing %q:\n%s", required, view)
		}
	}
	assertLinesFit(t, view, 140)
}

func TestUnconfiguredIdleViewShowsProviderOnboarding(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.status.MockMode = true
	m.status.CredentialsPresent = false
	m.status.AuthMode = "api_key"
	m.modes = []client.ProviderMode{
		{Mode: "api_key", Label: "API key", Available: false, Active: true},
		{Mode: "oauth_import", Label: "Codex OAuth", Available: true},
		{Mode: "claude_code", Label: "Claude Code", Available: true},
	}

	view := plain(m.View())
	for _, expected := range []string{
		"CONFIGURE PROVIDER", "API KEY", "CODEX OAUTH", "CLAUDE CODE", "ctrl+p configure",
	} {
		if !strings.Contains(view, expected) {
			t.Fatalf("onboarding missing %q:\n%s", expected, view)
		}
	}
}

func TestEnterSubmitsFromFocusedComposer(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.composer.SetValue("analyse the codebase")
	updated, cmd := m.handleKey(tea.KeyMsg{Type: tea.KeyEnter})
	got := updated.(model)
	if cmd == nil || !got.submitting {
		t.Fatalf("enter did not submit: cmd=%v submitting=%v", cmd, got.submitting)
	}
	if len(got.items) == 0 || !strings.Contains(plain(renderTranscript(got.items, 100)), "analyse the codebase") {
		t.Fatalf("user turn not appended immediately: %#v", got.items)
	}
}

func TestAltEnterInsertsNewlineWithoutSubmitting(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.composer.SetValue("line one")
	m.composer.SetCursor(len("line one"))
	updated, cmd := m.handleKey(tea.KeyMsg{Type: tea.KeyEnter, Alt: true})
	got := updated.(model)
	if cmd == nil {
		t.Fatal("alt+enter must route through the textarea")
	}
	if got.submitting {
		t.Fatal("alt+enter submitted the turn")
	}
}

func TestActiveConversationUsesTranscriptComposerAndContext(t *testing.T) {
	m := chatReadyModel(140, 40)
	m.items = []transcriptItem{
		{kind: itemUser, text: "analyse the codebase"},
		{kind: itemAssistant, text: "Reading project structure"},
	}
	m.showSidebar = true
	m.layout()
	view := plain(m.View())
	for _, required := range []string{
		"SESSION", "analyse the codebase", "ATLAS", "Reading project structure",
		"CONTEXT", "surface-chat",
	} {
		if !strings.Contains(view, required) {
			t.Fatalf("active view missing %q:\n%s", required, view)
		}
	}
	if strings.Contains(view, "provider modes") || strings.Contains(view, "missions") {
		t.Fatalf("active view regressed to dashboard:\n%s", view)
	}
	assertLinesFit(t, view, 140)
}

func TestCtrlCCancelsActiveWorkBeforeExit(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.surface.OwnerToken = "owner-1"
	m.streaming = true

	updated, cmd := m.handleKey(tea.KeyMsg{Type: tea.KeyCtrlC})
	got := updated.(model)
	if cmd == nil || !got.cancelRequested {
		t.Fatalf("ctrl+c did not request cancellation: cmd=%v requested=%v", cmd, got.cancelRequested)
	}
	if !strings.Contains(plain(renderTranscript(got.items, 100)), "CANCEL REQUESTED") {
		t.Fatalf("cancellation is not visible: %#v", got.items)
	}
}
