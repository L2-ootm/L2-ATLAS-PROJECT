package tui

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"atlas-tui/internal/client"
)

func TestApprovalOverlayOffersAllScopesAndCapsPreview(t *testing.T) {
	lines := make([]string, 12)
	for index := range lines {
		lines[index] = "line"
	}
	overlay := newApprovalOverlay(client.ToolApproval{
		ID: "approval-1", ToolName: "terminal", Args: strings.Join(lines, "\n"),
	})
	view := plain(overlay.view(100))
	for _, label := range []string{
		"Allow once", "Allow for this session",
		"Always allow this exact action", "Deny",
	} {
		if !strings.Contains(view, label) {
			t.Fatalf("overlay missing %q:\n%s", label, view)
		}
	}
	if strings.Count(view, "line") != 10 || !strings.Contains(view, "…") {
		t.Fatalf("preview is not capped at 10 lines:\n%s", view)
	}
}

func TestApprovalOverlayNumberAndEscapeResolveDeterministically(t *testing.T) {
	approval := client.ToolApproval{ID: "approval-1"}
	overlay := newApprovalOverlay(approval)
	_, result := overlay.update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'2'}})
	if result == nil || result.value != "session" || result.denied {
		t.Fatalf("unexpected session result: %+v", result)
	}

	overlay = newApprovalOverlay(approval)
	_, result = overlay.update(tea.KeyMsg{Type: tea.KeyEsc})
	if result == nil || !result.denied {
		t.Fatalf("escape must deny: %+v", result)
	}
}

func TestClarifyAndConfirmOverlaysHaveBlockingSelections(t *testing.T) {
	clarify := newClarifyOverlay("Choose a target", []string{"A", "B"})
	_, result := clarify.update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'1'}})
	if result == nil || result.value != "A" {
		t.Fatalf("unexpected clarify result: %+v", result)
	}

	confirm := newConfirmOverlay("Delete artifact?")
	_, result = confirm.update(tea.KeyMsg{Type: tea.KeyEnter})
	if result == nil || result.value != "no" || !result.denied {
		t.Fatalf("confirm must default safe: %+v", result)
	}
}

func TestActiveOverlayBlocksBackgroundKeyRouting(t *testing.T) {
	m := readyModel(100, 30)
	m.overlay = newConfirmOverlay("Proceed?")
	m.missions = append(m.missions, client.Mission{ID: "mission-2"})
	m.cursor = 0
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyDown})
	got := updated.(model)
	if got.cursor != 0 {
		t.Fatalf("background mission cursor moved under overlay: %d", got.cursor)
	}
}

func TestSurfacePromptEventsCreateClarifyAndConfirmOverlays(t *testing.T) {
	clarify := overlayFromSurfaceEvent(client.SurfaceEvent{
		PayloadJSON: `{"request_type":"clarify.request","prompt":"Choose","options":["A","B"]}`,
	})
	if clarify == nil || clarify.kind != overlayClarify {
		t.Fatalf("clarify event not routed: %+v", clarify)
	}
	confirm := overlayFromSurfaceEvent(client.SurfaceEvent{
		PayloadJSON: `{"type":"confirm.request","question":"Delete?"}`,
	})
	if confirm == nil || confirm.kind != overlayConfirm {
		t.Fatalf("confirm event not routed: %+v", confirm)
	}
}
