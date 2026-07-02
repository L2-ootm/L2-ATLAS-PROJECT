package tui

import (
	"strings"
	"testing"
)

func TestSlashSettingsOpensProviderOverlay(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.composer.SetValue("/settings")
	updated, cmd := m.submitComposer()
	got := updated.(model)
	if cmd == nil || got.focus != focusSettings || !got.settingsLoading {
		t.Fatalf("/settings did not open settings: focus=%v loading=%v cmd=%v", got.focus, got.settingsLoading, cmd)
	}
	if len(got.log) != 0 {
		t.Fatalf("command leaked into transcript: %#v", got.log)
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
	if !handled || len(updated.log) == 0 ||
		!strings.Contains(plain(updated.log[len(updated.log)-1]), "/settings") {
		t.Fatalf("/help did not render command reference: %#v", updated.log)
	}
}

func TestSecondTurnPreservesVisibleConversation(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.log = []string{"YOU  first prompt", "ATLAS  first answer"}
	m.composer.SetValue("second prompt")

	updated, cmd := m.submitComposer()
	got := updated.(model)
	if cmd == nil {
		t.Fatal("second turn did not dispatch")
	}
	view := plain(strings.Join(got.log, "\n"))
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
