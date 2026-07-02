package tui

// starfield.go — ambient idle-screen animation reimplementing the MiMo Code
// home patterns ATLAS-native (see ATTRIBUTION.md): a static field of
// twinkling stars, a periodic meteor streaking down-left from the top edge,
// and a pulsing gradient on the logo. Everything derives from one shared
// animation frame, so there is no per-tick mutable particle state and no
// new dependency.

import (
	"sort"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// star is one ambient particle: a fixed cell whose brightness twinkles.
type star struct {
	col, row int
	phase    int
	accent   bool
}

// starCycle is the twinkle period in animation frames.
const starCycle = 14

// buildStarfield seeds a deterministic sparse particle set for a viewport.
// A tiny xorshift PRNG keeps the field stable per size; resize regenerates.
func buildStarfield(width, height int, seed uint64) []star {
	if width < 40 || height < 8 {
		return nil
	}
	count := width * height / 220
	if count > 72 {
		count = 72
	}
	rng := seed | 1
	next := func(n int) int {
		rng ^= rng << 13
		rng ^= rng >> 7
		rng ^= rng << 17
		return int(rng % uint64(n))
	}
	stars := make([]star, 0, count)
	for i := 0; i < count; i++ {
		stars = append(stars, star{
			col:    next(width),
			row:    next(height),
			phase:  next(starCycle),
			accent: next(9) == 0,
		})
	}
	return stars
}

// placedStar is a particle resolved for one frame: column + styled glyph.
type placedStar struct {
	col  int
	text string
}

// starGlyph maps a star's twinkle position to its glyph and style. The dark
// tail of the cycle makes the field breathe instead of sitting static.
func starGlyph(s star, frame int) (string, lipgloss.Style, bool) {
	t := (frame + s.phase) % starCycle
	switch {
	case t < 6:
		return gl.starDim, styleDim, true
	case t < 9:
		return gl.starSoft, styleMuted, true
	case t < 11:
		if s.accent {
			return gl.starBright, styleKey, true
		}
		return gl.starBright, styleVal, true
	default:
		return "", styleDim, false
	}
}

// Meteor cadence: one streak roughly every 12s at the 300ms tick, alive for
// the first meteorLife frames of each cycle.
const (
	meteorPeriod = 40
	meteorLife   = 16
	meteorTail   = 6
)

// meteorCells rasterizes the ambient meteor for one frame: a bright head
// with a fading tail travelling down-left from near the top-right edge.
// Fully frame-derived; the spawn column varies per cycle.
func meteorCells(width, height, frame int) map[int][]placedStar {
	if width < 40 || height < 8 {
		return nil
	}
	t := frame % meteorPeriod
	if t >= meteorLife {
		return nil
	}
	cycle := uint64(frame/meteorPeriod)*2654435761 + 0x9e3779b9
	startX := width - 2 - int(cycle%uint64(max(1, width/4)))
	startY := int((cycle >> 8) % 3)
	cells := make(map[int][]placedStar)
	for i := 0; i < meteorTail; i++ {
		x := startX - (t-i)*2
		y := startY + (t - i)
		if t-i < 0 || x < 0 || x >= width || y < 0 || y >= height {
			continue
		}
		glyph, style := gl.starDim, styleDim
		switch {
		case i == 0:
			glyph, style = gl.starBright, styleVal
		case i < 3:
			glyph, style = gl.starSoft, styleKey
		}
		cells[y] = append(cells[y], placedStar{col: x, text: style.Render(glyph)})
	}
	return cells
}

// fieldCells resolves the full particle layer (stars + meteor) for a frame,
// grouped by row and column-sorted for row composition.
func fieldCells(stars []star, width, height, frame int) map[int][]placedStar {
	byRow := make(map[int][]placedStar)
	for _, s := range stars {
		if s.row >= height || s.col >= width {
			continue
		}
		if glyph, style, ok := starGlyph(s, frame); ok {
			byRow[s.row] = append(byRow[s.row], placedStar{col: s.col, text: style.Render(glyph)})
		}
	}
	for row, cells := range meteorCells(width, height, frame) {
		byRow[row] = append(byRow[row], cells...)
	}
	for row := range byRow {
		cells := byRow[row]
		sort.Slice(cells, func(i, j int) bool { return cells[i].col < cells[j].col })
	}
	return byRow
}

// composeRow renders one screen row: particle cells plus an optional hero
// line placed at column left. Particles within a 2-column gutter of the hero
// segment are dropped so the identity stays crisp. Never exceeds width cells.
func composeRow(width int, cells []placedStar, line string, left int) string {
	lineWidth := 0
	exL, exR := width, width
	if line != "" {
		lineWidth = lipgloss.Width(line)
		exL = max(0, left-2)
		exR = min(width, left+lineWidth+2)
	}
	var b strings.Builder
	pos := 0
	emit := func(cell placedStar) {
		if cell.col < pos || cell.col >= width {
			return
		}
		b.WriteString(strings.Repeat(" ", cell.col-pos))
		b.WriteString(cell.text)
		pos = cell.col + 1
	}
	for _, cell := range cells {
		if cell.col >= exL {
			continue
		}
		emit(cell)
	}
	if line != "" {
		if left > pos {
			b.WriteString(strings.Repeat(" ", left-pos))
		}
		b.WriteString(line)
		pos = left + lineWidth
		for _, cell := range cells {
			if cell.col < exR {
				continue
			}
			emit(cell)
		}
	}
	return b.String()
}

// starfieldCanvas centers the hero block vertically and each hero line
// horizontally over the animated field, mirroring lipgloss.Place semantics
// while keeping the field alive in the margins.
func starfieldCanvas(width, height int, hero string, stars []star, frame int) string {
	lines := strings.Split(hero, "\n")
	heroH := len(lines)
	top := max(0, (height-heroH)/2)
	byRow := fieldCells(stars, width, height, frame)
	rows := make([]string, 0, height)
	for row := 0; row < height; row++ {
		line := ""
		left := 0
		if row >= top && row-top < heroH {
			line = lines[row-top]
			left = max(0, (width-lipgloss.Width(line))/2)
		}
		rows = append(rows, composeRow(width, byRow[row], line, left))
	}
	return strings.Join(rows, "\n")
}

// logoPulseRamps holds the breathing gradient: dim -> base -> bright -> base.
var logoPulseRamps = [][]lipgloss.Color{
	{colVioletDim, colVioletDim, colViolet, colViolet, colBlueDim, colBlueDim},
	{colViolet, colViolet, colVioletSoft, colVioletSoft, colBlue, colBlue},
	{colVioletSoft, colVioletSoft, colVioletGlow, colVioletGlow, colBlueGlow, colBlueGlow},
	{colViolet, colViolet, colVioletSoft, colVioletSoft, colBlue, colBlue},
}

// pulseLogoRows applies the frame-selected ramp so the idle logo breathes
// through the violet->blue L2 voice (full period ~2.4s at the 300ms tick).
func pulseLogoRows(frame int) []string {
	rows := unicodeLogoRows
	if gl.ascii {
		rows = asciiLogoRows
	}
	ramp := logoPulseRamps[(frame/2)%len(logoPulseRamps)]
	out := make([]string, len(rows))
	for i, row := range rows {
		color := ramp[min(i, len(ramp)-1)]
		out[i] = lipgloss.NewStyle().Foreground(color).Render(row)
	}
	return out
}
