package tui

import (
	"os"
	"runtime"

	"github.com/charmbracelet/lipgloss"
)

// glyphSet holds the decorative runes the workbench draws. Modern emulators get
// the opencode-grade Unicode set; legacy Windows consoles (no WT_SESSION) get an
// ASCII fallback so the TUI never renders mojibake on cmd.exe/conhost.
type glyphSet struct {
	live     string // streaming indicator
	ellipsis string // truncation / "more" marker
	prompt   string // composer line prefix
	paneBar  string // active-pane marker
	submit   string // mission-submit marker
	bullet   string // audit-event bullet
	dash     string // run-boundary rule
	ascii    bool
}

var gl = pickGlyphs()

// pickGlyphs auto-selects ASCII on legacy Windows consoles. Override either way
// with ATLAS_TUI_ASCII=1 (force ASCII) or ATLAS_TUI_UNICODE=1 (force Unicode).
func pickGlyphs() glyphSet {
	ascii := false
	if runtime.GOOS == "windows" && os.Getenv("WT_SESSION") == "" && os.Getenv("ATLAS_TUI_UNICODE") == "" {
		ascii = true
	}
	if os.Getenv("ATLAS_TUI_ASCII") != "" {
		ascii = true
	}
	if os.Getenv("ATLAS_TUI_UNICODE") != "" {
		ascii = false
	}
	if ascii {
		return glyphSet{live: "*", ellipsis: "...", prompt: "| ", paneBar: "|", submit: ">>", bullet: "-", dash: "--", ascii: true}
	}
	return glyphSet{live: "●", ellipsis: "…", prompt: "┃ ", paneBar: "▌", submit: "»", bullet: "•", dash: "—"}
}

// L2 design-system palette (Electric Violet / Cyber Blue / Titanium White, HUD voice).
var (
	colViolet = lipgloss.Color("#7F00FF")
	colBlue   = lipgloss.Color("#00F0FF")
	colWhite  = lipgloss.Color("#E0E0E0")
	colMuted  = lipgloss.Color("#85858F")
	colGood   = lipgloss.Color("#00FF94")
	colWarn   = lipgloss.Color("#FFD600")
	colBad    = lipgloss.Color("#FF0055")

	styleTitle       = lipgloss.NewStyle().Bold(true).Foreground(colViolet)
	styleVioletStyle = lipgloss.NewStyle().Foreground(colViolet)
	styleKey         = lipgloss.NewStyle().Foreground(colBlue)
	styleMuted       = lipgloss.NewStyle().Foreground(colMuted)
	styleGood        = lipgloss.NewStyle().Foreground(colGood)
	styleWarn        = lipgloss.NewStyle().Foreground(colWarn)
	styleBad         = lipgloss.NewStyle().Foreground(colBad)
	styleVal         = lipgloss.NewStyle().Foreground(colWhite)

	styleSelected = lipgloss.NewStyle().Foreground(colWhite).Background(colViolet).Bold(true)
	styleHUD      = lipgloss.NewStyle().Foreground(colMuted).Bold(true)
)

var asciiBorder = lipgloss.Border{
	Top: "-", Bottom: "-", Left: "|", Right: "|",
	TopLeft: "+", TopRight: "+", BottomLeft: "+", BottomRight: "+",
}

func panelStyle(width int) lipgloss.Style {
	border := lipgloss.RoundedBorder()
	if gl.ascii {
		border = asciiBorder
	}
	return lipgloss.NewStyle().
		Border(border).
		BorderForeground(colMuted).
		Padding(0, 1).
		Width(width)
}
