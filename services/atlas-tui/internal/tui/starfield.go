package tui

// starfield.go — Go port of the MIT-licensed MiMo Code home presentation
// mechanics (see ATTRIBUTION.md): a static field of
// twinkling stars, a periodic meteor streaking down-left from the top edge,
// and a pulsing gradient on the logo. Everything derives from one shared
// animation frame, so there is no per-tick mutable particle state and no
// new dependency.

import (
	"fmt"
	"math"
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

// Stars update every 200 ms on the shared 50 ms render clock, matching the
// MiMoCode home screen without slowing meteor or gradient motion.
const starTwinkleFrames = 4

// starCycle is the twinkle period in twinkle frames.
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
	t := (frame/starTwinkleFrames + s.phase) % starCycle
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

// MiMoCode reference cadence: one streak every 8 seconds, alive for 3.6
// seconds, with a long fading tail. Values are 50 ms animation frames.
const (
	meteorPeriod = 160
	meteorLife   = 72
	meteorTail   = 32
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

// starfieldCanvas centers the hero as one block. Individual alignment belongs
// to the block itself; this keeps autocomplete rows anchored to the same left
// edge instead of independently centering every command and description.
func starfieldCanvas(width, height int, hero string, stars []star, frame int) string {
	lines := strings.Split(hero, "\n")
	heroH := len(lines)
	top := max(0, (height-heroH)/2)
	heroW := 0
	for _, line := range lines {
		heroW = max(heroW, lipgloss.Width(line))
	}
	blockLeft := max(0, (width-heroW)/2)
	byRow := fieldCells(stars, width, height, frame)
	rows := make([]string, 0, height)
	for row := 0; row < height; row++ {
		line := ""
		left := 0
		if row >= top && row-top < heroH {
			line = lines[row-top]
			left = blockLeft
		}
		rows = append(rows, composeRow(width, byRow[row], line, left))
	}
	return strings.Join(rows, "\n")
}

const logoPulsePeriod = 92 // 4.6 seconds at 50 ms, matching MiMoCode.

type rgbColor struct {
	r, g, b float64
}

var (
	logoViolet = rgbColor{127, 0, 255}
	logoCyan   = rgbColor{0, 240, 255}
	logoWhite  = rgbColor{224, 224, 224}
)

// pulseLogoRows renders a continuous horizontal violet-to-cyan gradient with
// a soft travelling highlight. Coloring each visible glyph removes the hard
// row bands from the earlier version while preserving the ATLAS palette.
func pulseLogoRows(frame int) []string {
	rows := unicodeLogoRows
	if gl.ascii {
		rows = asciiLogoRows
	}
	out := make([]string, len(rows))
	for i, row := range rows {
		runes := []rune(row)
		var b strings.Builder
		for col, glyph := range runes {
			if glyph == ' ' {
				b.WriteRune(glyph)
				continue
			}
			position := float64(col) / float64(max(1, len(runes)-1))
			color := logoGradientColor(position, frame)
			b.WriteString(lipgloss.NewStyle().Foreground(color).Render(string(glyph)))
		}
		out[i] = b.String()
	}
	return out
}

func logoGradientColor(position float64, frame int) lipgloss.Color {
	base := mixRGB(logoViolet, logoCyan, clamp01(position))
	phase := 2 * math.Pi * float64(frame%logoPulsePeriod) / logoPulsePeriod
	center := 0.5 + 0.42*math.Sin(phase)
	distance := (position - center) / 0.22
	highlight := math.Exp(-(distance * distance))
	breath := 0.08 + 0.20*(0.5+0.5*math.Sin(phase-math.Pi/2))*highlight
	return rgbToColor(mixRGB(base, logoWhite, breath))
}

func mixRGB(a, b rgbColor, amount float64) rgbColor {
	amount = clamp01(amount)
	return rgbColor{
		r: a.r + (b.r-a.r)*amount,
		g: a.g + (b.g-a.g)*amount,
		b: a.b + (b.b-a.b)*amount,
	}
}

func clamp01(value float64) float64 {
	return math.Max(0, math.Min(1, value))
}

func rgbToColor(color rgbColor) lipgloss.Color {
	return lipgloss.Color(fmt.Sprintf(
		"#%02X%02X%02X",
		int(math.Round(color.r)),
		int(math.Round(color.g)),
		int(math.Round(color.b)),
	))
}
