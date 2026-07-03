package tui

import (
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

func TestIdleAnimationCadenceMatchesMiMoReference(t *testing.T) {
	if animInterval != 50*time.Millisecond {
		t.Fatalf("animation cadence = %s, want 50ms", animInterval)
	}
}

func TestBuildStarfieldIsDeterministicPerSeed(t *testing.T) {
	a := buildStarfield(120, 30, starSeed)
	b := buildStarfield(120, 30, starSeed)
	if len(a) == 0 {
		t.Fatal("no stars generated for a normal viewport")
	}
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("star %d differs across identical seeds: %#v vs %#v", i, a[i], b[i])
		}
	}
	if tiny := buildStarfield(20, 4, starSeed); tiny != nil {
		t.Fatalf("tiny viewport must not generate stars, got %d", len(tiny))
	}
}

func TestComposeRowExcludesHeroGutterAndFitsWidth(t *testing.T) {
	cells := []placedStar{
		{col: 2, text: "*"}, {col: 18, text: "*"}, {col: 30, text: "*"}, {col: 58, text: "*"},
	}
	row := composeRow(60, cells, "HERO", 20)
	if lineWidth := len([]rune(plain(row))); lineWidth > 60 {
		t.Fatalf("row exceeds width: %d > 60", lineWidth)
	}
	stripped := plain(row)
	if !strings.Contains(stripped, "HERO") {
		t.Fatalf("hero line missing: %q", stripped)
	}
	// col 18 sits inside the left gutter (left-2) and col 30 would overlap
	// spacing right of HERO end but is outside exR=26, so it survives.
	if strings.Count(stripped, "*") != 3 {
		t.Fatalf("expected gutter star dropped, got %q", stripped)
	}
}

func TestStarfieldCanvasAlignsHeroAsOneBlock(t *testing.T) {
	canvas := plain(starfieldCanvas(40, 8, "123456789\nabc", nil, 0))
	lines := strings.Split(canvas, "\n")
	first := strings.Index(lines[3], "123456789")
	second := strings.Index(lines[4], "abc")
	if first < 0 || second < 0 {
		t.Fatalf("hero lines missing:\n%s", canvas)
	}
	if first != second {
		t.Fatalf("hero lines are independently centered: first=%d second=%d\n%s", first, second, canvas)
	}
}

func TestIdleViewAnimatesWithinWidthAcrossFrames(t *testing.T) {
	m := chatReadyModel(120, 36)
	if len(m.stars) == 0 {
		t.Fatal("layout did not seed the starfield")
	}
	var first string
	changed := false
	for frame := 0; frame < 24; frame++ {
		m.animFrame = frame
		view := m.View()
		stripped := plain(view)
		for _, required := range []string{"L2 // ATLAS", "MESSAGE ATLAS"} {
			if !strings.Contains(stripped, required) {
				t.Fatalf("frame %d missing %q", frame, required)
			}
		}
		assertLinesFit(t, stripped, 120)
		if first == "" {
			first = view
		} else if view != first {
			changed = true
		}
	}
	if !changed {
		t.Fatal("idle view is static across 24 animation frames")
	}
}

func TestPulseLogoBreathesWithoutChangingGlyphs(t *testing.T) {
	if logoPulsePeriod != 92 {
		t.Fatalf("logo pulse period = %d frames, want 92", logoPulsePeriod)
	}
	if left, right := logoGradientColor(0, 0), logoGradientColor(1, 0); left == right {
		t.Fatalf("logo gradient collapsed to one color: %s", left)
	}
	if start, quarter := logoGradientColor(0.5, 0), logoGradientColor(0.5, logoPulsePeriod/4); start == quarter {
		t.Fatalf("logo highlight does not travel: %s", start)
	}
	for _, frame := range []int{0, logoPulsePeriod / 4, logoPulsePeriod / 2, logoPulsePeriod - 1} {
		if got, want := plain(strings.Join(pulseLogoRows(frame), "\n")),
			plain(strings.Join(pulseLogoRows(0), "\n")); got != want {
			t.Fatalf("logo glyphs changed at frame %d", frame)
		}
	}
}

func TestTabCyclesAgentModeInComposer(t *testing.T) {
	m := chatReadyModel(120, 36)
	updated, _ := m.handleKey(tea.KeyMsg{Type: tea.KeyTab})
	got := updated.(model)
	if got.mode != modePlan {
		t.Fatalf("tab did not advance mode: %v", got.mode)
	}
	updated, _ = got.handleKey(tea.KeyMsg{Type: tea.KeyShiftTab})
	got = updated.(model)
	if got.mode != modeBuild {
		t.Fatalf("shift+tab did not reverse mode: %v", got.mode)
	}
}

func TestModeWrapsIntentButNotDisplay(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.mode = modePlan
	m.composer.SetValue("refactor the auth layer")
	updated, cmd := m.handleKey(tea.KeyMsg{Type: tea.KeyEnter})
	got := updated.(model)
	if cmd == nil || !got.submitting {
		t.Fatal("plan-mode submit did not dispatch")
	}
	rendered := plain(renderTranscript(got.items, 100))
	if !strings.Contains(rendered, "refactor the auth layer") {
		t.Fatalf("user turn missing raw text: %q", rendered)
	}
	if strings.Contains(rendered, "PLAN MODE") {
		t.Fatalf("intent wrapper leaked into the visible transcript: %q", rendered)
	}
	if !strings.Contains(modePlan.wrapIntent("x"), "PLAN MODE") {
		t.Fatal("plan wrapper missing its contract text")
	}
}

func TestWorkflowCommandDispatchesMission(t *testing.T) {
	m := chatReadyModel(120, 36)
	handled, got, cmd := m.executeSlashCommand("/deep-research provider mesh tradeoffs")
	if !handled || cmd == nil || !got.submitting {
		t.Fatalf("workflow did not dispatch: handled=%v cmd=%v submitting=%v",
			handled, cmd, got.submitting)
	}
	rendered := plain(renderTranscript(got.items, 100))
	if !strings.Contains(rendered, "/deep-research provider mesh tradeoffs") {
		t.Fatalf("workflow user turn missing: %q", rendered)
	}
}

func TestWorkflowCommandRequiresArgsWhenDeclared(t *testing.T) {
	m := chatReadyModel(120, 36)
	handled, got, _ := m.executeSlashCommand("/deep-research")
	if !handled || got.submitting {
		t.Fatalf("argless workflow must not dispatch: handled=%v submitting=%v",
			handled, got.submitting)
	}
	if !strings.Contains(plain(renderTranscript(got.items, 100)), "usage: /deep-research") {
		t.Fatal("usage hint missing")
	}
}

func TestModeSlashCommandSetsNamedMode(t *testing.T) {
	m := chatReadyModel(120, 36)
	handled, got, _ := m.executeSlashCommand("/mode compose")
	if !handled || got.mode != modeCompose {
		t.Fatalf("/mode compose failed: handled=%v mode=%v", handled, got.mode)
	}
	handled, got, _ = got.executeSlashCommand("/mode nonsense")
	if !handled || got.mode != modeCompose {
		t.Fatal("unknown mode name must not change the mode")
	}
}
