package tui

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"unicode/utf8"

	"github.com/charmbracelet/lipgloss"

	"atlas-tui/internal/client"
)

func TestCreateSurfaceGatesOwnedApprovalPolling(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Path != "/v1/surface-sessions" {
			http.NotFound(w, r)
			return
		}
		_, _ = w.Write([]byte(`{"id":"surface-1","surface":{"kind":"tui","session_id":"tui-1"},"workspace":{"kind":"global","root":"C:\\atlas"},"agent":"native","model":{"provider":"openrouter","model_id":"test"},"permission_mode":"ask","state":"active","owner_token":"owner-1"}`))
	}))
	defer srv.Close()

	m := New(client.New(srv.URL), srv.URL)
	msg := m.createSurface()()
	updated, cmd := m.Update(msg)
	got := updated.(model)
	if got.surface.ID != "surface-1" || got.surface.OwnerToken != "owner-1" {
		t.Fatalf("surface not retained: %+v", got.surface)
	}
	if cmd == nil {
		t.Fatal("surface creation must start scoped approval polling")
	}
}

func TestCreateSurfaceShowsGatewayUpgradeRemediation(t *testing.T) {
	srv := httptest.NewServer(http.NotFoundHandler())
	defer srv.Close()

	m := New(client.New(srv.URL), srv.URL)
	updated, _ := m.Update(m.createSurface()())
	got := updated.(model)
	if !strings.Contains(got.errMsg, "upgrade") || !strings.Contains(got.errMsg, "gateway") {
		t.Fatalf("missing gateway upgrade remediation: %q", got.errMsg)
	}
}

func TestClaudeCodeModeDispatchesClaudeCodeAgent(t *testing.T) {
	var agent string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		agent, _ = body["agent"].(string)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run":{"id":"run-1"},"executing":true}`))
	}))
	defer srv.Close()

	m := New(client.New(srv.URL), srv.URL)
	m.status.AuthMode = "claude_code"
	m.surface.ID = "surface-1"
	msg := m.startRun("mission-1")()
	if started, ok := msg.(runStartedMsg); !ok || started.err != nil {
		t.Fatalf("unexpected start message: %#v", msg)
	}
	if agent != "claude_code" {
		t.Fatalf("agent = %q, want claude_code", agent)
	}
}

func readyModel(width, height int) model {
	m := New(nil, "http://127.0.0.1:8484")
	m.phase = phaseReady
	m.status = client.ProviderStatus{
		Provider: "openrouter", Model: "test/model", AuthMode: "api_key",
	}
	m.modes = []client.ProviderMode{
		{Mode: "api_key", Available: true, Active: true},
		{Mode: "oauth_import", Available: true},
		{Mode: "claude_code", Available: false},
		{Mode: "freellmapi", Available: true},
	}
	m.missions = []client.Mission{
		{ID: "mission-1", Title: "Render the operator workbench", Status: "running"},
	}
	m.approvals = []client.ToolApproval{
		{ID: "approval-1", ToolName: "terminal", RiskLevel: "high", Summary: "run tests"},
	}
	m.log = []string{"assistant hello", "tool terminal go test ./..."}
	m.width, m.height = width, height
	m.layout()
	return m
}

func TestASCIIViewContainsOnlyASCIIAndFitsNarrowTerminal(t *testing.T) {
	original := gl
	t.Setenv("ATLAS_TUI_ASCII", "1")
	t.Setenv("ATLAS_TUI_UNICODE", "")
	gl = pickGlyphs()
	t.Cleanup(func() { gl = original })

	view := plain(readyModel(80, 24).View())
	if strings.Contains(view, "| |") {
		t.Fatalf("composer renders duplicate prompt rails:\n%s", view)
	}
	for _, r := range view {
		if r > utf8.RuneSelf {
			t.Fatalf("ASCII view contains non-ASCII rune %q in:\n%s", r, view)
		}
	}
	assertLinesFit(t, view, 80)
}

func TestUnicodeViewUsesNativeGlyphsAndFitsWideTerminal(t *testing.T) {
	original := gl
	t.Setenv("ATLAS_TUI_ASCII", "")
	t.Setenv("ATLAS_TUI_UNICODE", "1")
	gl = pickGlyphs()
	t.Cleanup(func() { gl = original })

	view := plain(readyModel(140, 40).View())
	if strings.ContainsRune(view, '�') {
		t.Fatalf("Unicode view contains replacement rune:\n%s", view)
	}
	if !strings.Contains(view, "MESSAGE ATLAS") || !strings.Contains(view, "CONTEXT") {
		t.Fatalf("Unicode chat-first chrome missing:\n%s", view)
	}
	assertLinesFit(t, view, 140)
}

func TestSettingsViewIsSecretSafeAndFitsASCIIAndUnicode(t *testing.T) {
	for _, tc := range []struct {
		name   string
		ascii  bool
		width  int
		height int
	}{
		{name: "ascii-narrow", ascii: true, width: 80, height: 24},
		{name: "unicode-wide", width: 140, height: 40},
	} {
		t.Run(tc.name, func(t *testing.T) {
			original := gl
			if tc.ascii {
				t.Setenv("ATLAS_TUI_ASCII", "1")
				t.Setenv("ATLAS_TUI_UNICODE", "")
			} else {
				t.Setenv("ATLAS_TUI_ASCII", "")
				t.Setenv("ATLAS_TUI_UNICODE", "1")
			}
			gl = pickGlyphs()
			t.Cleanup(func() { gl = original })

			m := readyModel(tc.width, tc.height)
			form := newSettingsForm(testConfig(), nil)
			form.inputs[settingsAPIKey].SetValue("never-render-settings-secret")
			m.settings = &form
			m.focus = focusSettings
			view := plain(m.View())
			if strings.Contains(view, "never-render-settings-secret") {
				t.Fatalf("settings leaked API key:\n%s", view)
			}
			if strings.ContainsRune(view, '�') {
				t.Fatalf("settings view contains replacement rune:\n%s", view)
			}
			if tc.ascii {
				for _, r := range view {
					if r > utf8.RuneSelf {
						t.Fatalf("ASCII settings contains non-ASCII rune %q:\n%s", r, view)
					}
				}
			}
			assertLinesFit(t, view, tc.width)
		})
	}
}

func assertLinesFit(t *testing.T, view string, width int) {
	t.Helper()
	for i, line := range strings.Split(view, "\n") {
		if got := lipgloss.Width(line); got > width {
			t.Fatalf("line %d width = %d, terminal width = %d: %q", i+1, got, width, line)
		}
	}
}
