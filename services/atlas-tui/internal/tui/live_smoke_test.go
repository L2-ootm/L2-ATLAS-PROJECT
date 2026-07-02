package tui

import (
	"os"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"atlas-tui/internal/client"
)

// TestLiveConversationSmoke drives the real model Update loop against a live
// gateway (ATLAS_TUI_LIVE_GATEWAY) through a full conversational turn:
// surface session -> provider status -> submit -> mission -> run -> SSE ->
// transcript. It is the headless equivalent of acceptance criteria 3/4 of the
// chat-first intent doc. Skipped unless the operator points it at a gateway.
func TestLiveConversationSmoke(t *testing.T) {
	gateway := os.Getenv("ATLAS_TUI_LIVE_GATEWAY")
	if gateway == "" {
		t.Skip("set ATLAS_TUI_LIVE_GATEWAY=http://127.0.0.1:8484 to run")
	}

	c := client.New(gateway)
	m := New(c, gateway)
	m.width, m.height = 120, 36
	m.layout()

	drive := func(cmd tea.Cmd) {
		t.Helper()
		queue := []tea.Cmd{cmd}
		deadline := time.Now().Add(4 * time.Minute)
		for len(queue) > 0 {
			if time.Now().After(deadline) {
				t.Fatal("live smoke exceeded deadline")
			}
			next := queue[0]
			queue = queue[1:]
			if next == nil {
				continue
			}
			msg := next()
			switch typed := msg.(type) {
			case tea.BatchMsg:
				for _, sub := range typed {
					queue = append(queue, sub)
				}
				continue
			case spinnerTickMsg, pollTickMsg:
				continue // no rescheduling loops in headless mode
			case nil:
				continue
			}
			updated, follow := m.Update(msg)
			m = updated.(model)
			if follow != nil {
				queue = append(queue, follow)
			}
		}
	}

	drive(m.fetchStatus())
	drive(m.createSurface())
	if m.surface.ID == "" || m.surface.OwnerToken == "" {
		t.Fatalf("no owned surface session: %+v errMsg=%q", m.surface, m.errMsg)
	}

	readiness := readinessFor(m.status, mockAllowed())
	if !readiness.CanRun {
		t.Fatalf("provider not live: %+v", readiness)
	}

	m.composer.SetValue("Reply with one short sentence confirming the ATLAS TUI live smoke.")
	updated, cmd := m.submitComposer()
	m = updated.(model)
	drive(cmd)

	rendered := plain(renderTranscript(m.items, 100))
	if !strings.Contains(rendered, "live smoke") {
		t.Fatalf("user turn missing from transcript:\n%s", rendered)
	}
	var sawAssistant, sawRule bool
	for _, item := range m.items {
		if item.kind == itemAssistant && strings.TrimSpace(item.text) != "" {
			sawAssistant = true
		}
		if item.kind == itemRule && item.status != "failed" {
			sawRule = true
		}
	}
	if !sawAssistant {
		t.Fatalf("no assistant response rendered:\n%s", rendered)
	}
	if !sawRule {
		t.Fatalf("run did not terminate cleanly:\n%s", rendered)
	}
	if m.streaming || m.submitting {
		t.Fatalf("turn did not settle: streaming=%v submitting=%v", m.streaming, m.submitting)
	}
	t.Logf("live transcript:\n%s", rendered)

	drive(m.closeSurface())
}
