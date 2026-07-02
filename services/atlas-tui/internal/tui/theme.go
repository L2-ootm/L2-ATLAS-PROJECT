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
	live     string   // streaming indicator
	ellipsis string   // truncation / "more" marker
	prompt   string   // composer line prefix
	paneBar  string   // active-pane marker
	submit   string   // mission-submit marker
	bullet   string   // audit-event bullet
	dash     string   // run-boundary rule
	toolRun  string   // tool in flight
	toolOK   string   // tool completed
	toolBad  string   // tool failed
	diffMark string   // diff line marker
	codeBar  string   // code-block gutter
	spinner  []string // busy animation frames
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
		return glyphSet{
			live: "*", ellipsis: "...", prompt: "| ", paneBar: "|", submit: ">>",
			bullet: "-", dash: "--", toolRun: "~", toolOK: "+", toolBad: "x",
			diffMark: "+-", codeBar: "| ",
			spinner: []string{"|", "/", "-", "\\"},
			ascii:   true,
		}
	}
	return glyphSet{
		live: "●", ellipsis: "…", prompt: "┃ ", paneBar: "▌", submit: "»",
		bullet: "•", dash: "—", toolRun: "◐", toolOK: "✓", toolBad: "✗",
		diffMark: "±", codeBar: "│ ",
		spinner: []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"},
	}
}

// asciiLogo / unicodeLogo render the idle-screen ATLAS identity. Rows are
// colored violet->blue at render time for the L2 gradient voice.
var asciiLogoRows = []string{
	`    _  _____ _      _   ___ `,
	`   / \|_   _| |    / \ / __|`,
	`  / _ \ | | | |__ / _ \\__ \`,
	` /_/ \_\|_| |____/_/ \_|___/`,
}

var unicodeLogoRows = []string{
	" █████╗ ████████╗██╗      █████╗ ███████╗",
	"██╔══██╗╚══██╔══╝██║     ██╔══██╗██╔════╝",
	"███████║   ██║   ██║     ███████║███████╗",
	"██╔══██║   ██║   ██║     ██╔══██║╚════██║",
	"██║  ██║   ██║   ███████╗██║  ██║███████║",
	"╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝",
}

// logoRows picks the glyph-safe logo and applies the violet->blue ramp.
func logoRows() []string {
	rows := unicodeLogoRows
	if gl.ascii {
		rows = asciiLogoRows
	}
	ramp := []lipgloss.Color{colViolet, colViolet, colVioletSoft, colVioletSoft, colBlue, colBlue}
	out := make([]string, len(rows))
	for i, row := range rows {
		color := ramp[min(i, len(ramp)-1)]
		out[i] = lipgloss.NewStyle().Foreground(color).Render(row)
	}
	return out
}

// L2 design-system palette (Electric Violet / Cyber Blue / Titanium White, HUD voice).
var (
	colViolet     = lipgloss.Color("#7F00FF")
	colVioletSoft = lipgloss.Color("#9B4DFF")
	colBlue       = lipgloss.Color("#00F0FF")
	colWhite      = lipgloss.Color("#E0E0E0")
	colMuted      = lipgloss.Color("#85858F")
	colDim        = lipgloss.Color("#3A3A44")
	colGood       = lipgloss.Color("#00FF94")
	colWarn       = lipgloss.Color("#FFD600")
	colBad        = lipgloss.Color("#FF0055")

	styleTitle       = lipgloss.NewStyle().Bold(true).Foreground(colViolet)
	styleVioletStyle = lipgloss.NewStyle().Foreground(colViolet)
	styleKey         = lipgloss.NewStyle().Foreground(colBlue)
	styleMuted       = lipgloss.NewStyle().Foreground(colMuted)
	styleGood        = lipgloss.NewStyle().Foreground(colGood)
	styleWarn        = lipgloss.NewStyle().Foreground(colWarn)
	styleBad         = lipgloss.NewStyle().Foreground(colBad)
	styleVal         = lipgloss.NewStyle().Foreground(colWhite)
	styleCode        = lipgloss.NewStyle().Foreground(colBlue)
	styleCodeBlock   = lipgloss.NewStyle().Foreground(colVioletSoft)

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
