package tui

import "github.com/charmbracelet/lipgloss"

// L2 design-system palette (Electric Violet / Cyber Blue / Titanium White, HUD voice).
var (
	colViolet = lipgloss.Color("#7C5CFF")
	colBlue   = lipgloss.Color("#4F8BFF")
	colWhite  = lipgloss.Color("#EDEAE0")
	colMuted  = lipgloss.Color("#8A8FA3")
	colGood   = lipgloss.Color("#3DD68C")
	colWarn   = lipgloss.Color("#F2B65A")
	colBad    = lipgloss.Color("#FF6B6B")

	styleTitle = lipgloss.NewStyle().Bold(true).Foreground(colViolet)
	styleKey   = lipgloss.NewStyle().Foreground(colBlue)
	styleMuted = lipgloss.NewStyle().Foreground(colMuted)
	styleGood  = lipgloss.NewStyle().Foreground(colGood)
	styleWarn  = lipgloss.NewStyle().Foreground(colWarn)
	styleBad   = lipgloss.NewStyle().Foreground(colBad)
	styleVal   = lipgloss.NewStyle().Foreground(colWhite)

	stylePanel = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colMuted).
			Padding(0, 1)

	styleSelected = lipgloss.NewStyle().Foreground(colWhite).Background(colViolet).Bold(true)
)
