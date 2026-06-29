package tui

import (
	"strings"
	"testing"
	"unicode/utf8"

	"github.com/charmbracelet/lipgloss"

	"atlas-tui/internal/client"
)

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
	if !strings.Contains(view, "▌missions") {
		t.Fatalf("Unicode active-pane marker missing:\n%s", view)
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
