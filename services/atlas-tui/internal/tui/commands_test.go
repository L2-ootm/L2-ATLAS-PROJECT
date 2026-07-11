package tui

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"atlas-tui/internal/client"
)

func TestSlashSettingsOpensProviderOverlay(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.composer.SetValue("/settings")
	m.menuMatches = nil // direct submit path (menu handles its own enter)
	updated, cmd := m.submitComposer()
	got := updated.(model)
	if cmd == nil || got.focus != focusSettings || !got.settingsLoading {
		t.Fatalf("/settings did not open settings: focus=%v loading=%v cmd=%v", got.focus, got.settingsLoading, cmd)
	}
	if len(got.items) != 0 {
		t.Fatalf("command leaked into transcript: %#v", got.items)
	}
}

func TestSlashSidebarAndHelpStayInConversation(t *testing.T) {
	m := chatReadyModel(120, 36)
	initial := m.showSidebar
	handled, updated, _ := m.executeSlashCommand("/sidebar")
	if !handled || updated.showSidebar == initial {
		t.Fatal("/sidebar did not toggle context")
	}
	handled, updated, _ = updated.executeSlashCommand("/help")
	rendered := plain(renderTranscript(updated.items, 120))
	if !handled || len(updated.items) == 0 || !strings.Contains(rendered, "/settings") {
		t.Fatalf("/help did not render command reference: %q", rendered)
	}
}

func TestSecondTurnPreservesVisibleConversation(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.items = []transcriptItem{
		{kind: itemUser, text: "first prompt"},
		{kind: itemAssistant, text: "first answer"},
	}
	m.composer.SetValue("second prompt")

	updated, cmd := m.submitComposer()
	got := updated.(model)
	if cmd == nil {
		t.Fatal("second turn did not dispatch")
	}
	view := plain(renderTranscript(got.items, 120))
	for _, expected := range []string{"first prompt", "first answer", "second prompt"} {
		if !strings.Contains(view, expected) {
			t.Fatalf("visible conversation lost %q: %s", expected, view)
		}
	}
}

func TestNewClearsConversationWithoutReplayingSurfaceState(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.items = []transcriptItem{
		{kind: itemUser, text: "old prompt"},
		{kind: itemAssistant, text: "old answer"},
	}
	m.lastAssistantText = "old answer"
	m.viewport.SetContent("stale viewport")
	m.errMsg = "transient failure"
	m.lastSurfaceSeq = 42
	m.surface.OwnerToken = "owner-secret"
	m.approvals = []client.ToolApproval{
		{ID: "approval-1", ToolName: "terminal", Status: "pending"},
	}
	m.overlay = newApprovalOverlay(m.approvals[0])
	ownedSurface := m.surface
	ownedOverlay := m.overlay

	handled, updated, cmd := m.executeSlashCommand("/new")

	if !handled || cmd != nil {
		t.Fatalf("/new result: handled=%v cmd=%v", handled, cmd)
	}
	if len(updated.items) != 0 || updated.lastAssistantText != "" || updated.errMsg != "" {
		t.Fatalf(
			"conversation-local state survived: items=%d dedupe=%q err=%q",
			len(updated.items),
			updated.lastAssistantText,
			updated.errMsg,
		)
	}
	if strings.Contains(updated.viewport.View(), "stale viewport") {
		t.Fatalf("viewport was not cleared: %q", updated.viewport.View())
	}
	if updated.lastSurfaceSeq != 42 {
		t.Fatalf("surface cursor changed: got %d want 42", updated.lastSurfaceSeq)
	}
	if updated.surface != ownedSurface {
		t.Fatalf("owned surface changed: got %#v want %#v", updated.surface, ownedSurface)
	}
	if len(updated.approvals) != 1 || updated.approvals[0].ID != "approval-1" {
		t.Fatalf("owned approvals changed: %#v", updated.approvals)
	}
	if updated.overlay != ownedOverlay {
		t.Fatal("active overlay changed")
	}
}

func TestStreamCompletionReturnsComposerFocus(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.streaming = true
	m.composer.Blur()
	m.focus = focusMissions

	updated, _ := m.Update(streamDoneMsg{})
	got := updated.(model)
	if got.streaming || got.focus != focusComposer || !got.composer.Focused() {
		t.Fatalf("completion focus = %v focused=%v streaming=%v", got.focus, got.composer.Focused(), got.streaming)
	}
}

// --- command autocomplete menu ----------------------------------------------

func TestTypingSlashOpensFilteredCommandMenu(t *testing.T) {
	m := chatReadyModel(120, 36)
	updated, _ := m.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	got := updated.(model)
	if !got.menuOpen() || len(got.menuMatches) != len(slashCommands) {
		t.Fatalf("bare / must list all commands: %d", len(got.menuMatches))
	}
	updated, _ = got.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	got = updated.(model)
	for _, match := range got.menuMatches {
		if !strings.HasPrefix(match.name, "/s") {
			t.Fatalf("filter leaked %q", match.name)
		}
	}
	if !got.menuOpen() {
		t.Fatal("menu closed while a matching prefix is typed")
	}
}

func TestCommandMenuTabCompletesAndEnterExecutes(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.composer.SetValue("/side")
	m.syncMenu()
	if !m.menuOpen() {
		t.Fatal("menu did not open for /side")
	}
	handled, updated, _ := m.handleMenuKey(tea.KeyMsg{Type: tea.KeyTab})
	got := updated.(model)
	if !handled || got.composer.Value() != "/sidebar" {
		t.Fatalf("tab completion = %q", got.composer.Value())
	}

	initial := got.showSidebar
	handled, updated, _ = got.handleMenuKey(tea.KeyMsg{Type: tea.KeyEnter})
	got = updated.(model)
	if !handled || got.showSidebar == initial {
		t.Fatal("enter did not execute the selected command")
	}
	if got.composer.Value() != "" {
		t.Fatalf("composer not cleared after command: %q", got.composer.Value())
	}
}

func TestCommandMenuEscDismissesWithoutClearingDraft(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.composer.SetValue("/set")
	m.syncMenu()
	handled, updated, _ := m.handleMenuKey(tea.KeyMsg{Type: tea.KeyEsc})
	got := updated.(model)
	if !handled || got.menuOpen() {
		t.Fatal("esc did not dismiss the menu")
	}
	if got.composer.Value() != "/set" {
		t.Fatalf("draft lost on dismiss: %q", got.composer.Value())
	}
}

func TestMenuDoesNotOpenMidMessage(t *testing.T) {
	if matches := commandMatches("deploy /settings"); matches != nil {
		t.Fatalf("mid-message slash matched: %#v", matches)
	}
	if matches := commandMatches("/settings now"); matches != nil {
		t.Fatalf("slash with args matched menu: %#v", matches)
	}
}

func TestFormatMissionRowShowsIntentAndUpdatedDay(t *testing.T) {
	row := formatMissionRow(client.Mission{
		Status:    "succeeded",
		Title:     "Fix the seam",
		Intent:    "wire the donor TUI over the gateway adapter without a second backend",
		UpdatedAt: "2026-07-10T14:00:00Z",
	})
	want := "succeeded Fix the seam — wire the donor TUI over the gateway a... (2026-07-10)"
	if row != want {
		t.Fatalf("row = %q, want %q", row, want)
	}
}

func TestFormatMissionRowOmitsEmptyOrDuplicateIntent(t *testing.T) {
	row := formatMissionRow(client.Mission{Status: "pending", Title: "t", Intent: "t"})
	if row != "pending t" {
		t.Fatalf("row = %q", row)
	}
}
