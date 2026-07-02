package tui

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
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
