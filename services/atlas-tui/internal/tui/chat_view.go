package tui

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
)

const contextSidebarWidth = 32

func (m model) chatView() string {
	if len(m.items) == 0 && !m.busy() {
		return m.idleChatView()
	}
	return m.activeChatView()
}

// idleChatView is the MiMo-grade opening state: identity over the animated
// starfield, one focused composer, readiness or onboarding — no dashboard
// chrome.
func (m model) idleChatView() string {
	width := max(40, m.width)
	height := max(18, m.height-2)
	cardWidth := min(84, max(48, width-12))
	readiness := readinessFor(m.status, mockAllowed())

	var body strings.Builder
	for _, row := range pulseLogoRows(m.animFrame) {
		body.WriteString(row + "\n")
	}
	body.WriteString(styleHUD.Render("L2 // ATLAS "+gl.dash+" AGENT WORKBENCH") + "\n\n")
	body.WriteString(styleMuted.Render("MESSAGE ATLAS") + "\n")
	body.WriteString(m.composerSurface(cardWidth, readiness))
	body.WriteString("\n")
	if menu := m.commandMenuView(cardWidth); menu != "" {
		body.WriteString(menu + "\n")
	}
	if readiness.CanRun {
		body.WriteString(styleVal.Render(readiness.Label) +
			styleMuted.Render("  "+orDash(m.surface.PermissionMode)) + "\n")
		body.WriteString(styleMuted.Render("enter submit  tab mode  / commands"))
	} else {
		body.WriteString(onboardingNotice(m))
	}
	body.WriteString("\n\n" + m.tipLine())
	if m.errMsg != "" {
		body.WriteString("\n\n" + styleBad.Render(m.errMsg))
	}
	hero := body.String()
	if len(m.stars) == 0 {
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, hero) +
			"\n" + m.statusBar()
	}
	return starfieldCanvas(width, height, hero, m.stars, m.animFrame) +
		"\n" + m.statusBar()
}

// tipLine renders the rotating hint under the idle hero: mode-colored dot,
// Tip label, muted text.
func (m model) tipLine() string {
	dot := lipgloss.NewStyle().Foreground(m.mode.color()).Render(gl.live)
	return dot + styleHUD.Render(" Tip ") + styleMuted.Render(idleTip(m.animFrame))
}

func onboardingNotice(m model) string {
	rows := []string{styleWarn.Render("CONFIGURE PROVIDER")}
	for _, mode := range m.modes {
		label := strings.ToUpper(strings.TrimSpace(mode.Label))
		if label == "" {
			label = strings.ToUpper(strings.ReplaceAll(mode.Mode, "_", " "))
		}
		state := styleMuted.Render("MISSING")
		if mode.Available {
			state = styleGood.Render("READY")
		}
		if mode.Active {
			state = styleKey.Render("ACTIVE / ") + state
		}
		rows = append(rows, styleMuted.Render(fmt.Sprintf("%-18s", label))+" "+state)
	}
	rows = append(rows,
		styleVal.Render("ctrl+p configure")+styleMuted.Render("  mock requires ATLAS_TUI_ALLOW_MOCK=1"))
	// Pad every row to the block width so centered placement keeps the rows
	// left-aligned with each other instead of centering each line separately.
	widest := 0
	for _, row := range rows {
		widest = max(widest, lipgloss.Width(row))
	}
	for i, row := range rows {
		if pad := widest - lipgloss.Width(row); pad > 0 {
			rows[i] = row + strings.Repeat(" ", pad)
		}
	}
	return strings.Join(rows, "\n")
}

func (m model) activeChatView() string {
	header := m.compactHeader()
	transcript := m.transcriptView()
	composerWidth := max(30, m.viewport.Width)
	composer := m.composerSurface(composerWidth, readinessFor(m.status, mockAllowed()))
	sections := []string{header, "", transcript, "", composer}
	if menu := m.commandMenuView(composerWidth); menu != "" {
		sections = append(sections, menu)
	}
	main := strings.Join(sections, "\n")
	if m.showSidebar && m.width >= 110 {
		main = lipgloss.JoinHorizontal(
			lipgloss.Top,
			lipgloss.NewStyle().Width(max(40, m.width-contextSidebarWidth-4)).Render(main),
			"  ",
			m.contextSidebar(),
		)
	}
	return main + "\n" + m.statusBar()
}

func (m model) chatOverlayView() string {
	var b strings.Builder
	b.WriteString(m.compactHeader() + "\n\n")
	b.WriteString(styleHUD.Render("TRANSCRIPT") + "\n")
	tail := m.items
	if len(tail) > 5 {
		tail = tail[len(tail)-5:]
	}
	width := max(40, m.width-4)
	if rendered := renderTranscript(tail, width); rendered != "" {
		b.WriteString(rendered + "\n")
	}
	b.WriteString("\n" + m.overlay.view(m.width))
	b.WriteString("\n" + styleMuted.Render("decision active  arrows move  enter select  esc deny"))
	return b.String()
}

func (m model) compactHeader() string {
	readiness := readinessFor(m.status, mockAllowed())
	state := styleGood.Render(readiness.Label)
	if !readiness.CanRun {
		state = styleWarn.Render(readiness.Label)
	}
	line := styleTitle.Render("L2 // ATLAS") + "  " +
		styleHUD.Render("SESSION") + " " + styleVal.Render(short(m.surface.ID)) + "  " +
		styleVal.Render(orDash(m.status.Model)) + "  " + state
	if m.busy() {
		line += "  " + styleKey.Render(m.spinnerFrame()+" WORKING")
	}
	if m.errMsg != "" {
		line += "\n" + styleBad.Render("! "+m.errMsg)
	}
	return line
}

func (m model) spinnerFrame() string {
	frames := gl.spinner
	if len(frames) == 0 {
		return ""
	}
	return frames[m.spinFrame%len(frames)]
}

func (m model) transcriptView() string {
	title := styleHUD.Render("TRANSCRIPT")
	if m.streaming {
		title += "  " + styleKey.Render(gl.live+" LIVE")
	} else if m.submitting {
		title += "  " + styleWarn.Render("DISPATCHING")
	}
	if m.busy() && !m.turnStarted.IsZero() {
		title += "  " + styleMuted.Render(elapsedLabel(int(time.Since(m.turnStarted).Seconds())))
	}
	body := m.viewport.View()
	if strings.TrimSpace(body) == "" {
		body = styleMuted.Render("No events recorded. Operation window open.")
	}
	return title + "\n" + body
}

func (m model) contextSidebar() string {
	var b strings.Builder
	b.WriteString(styleHUD.Render("CONTEXT") + "\n\n")
	contextRow(&b, "SESSION", orDash(m.surface.ID))
	contextRow(&b, "STATE", orDash(m.surface.State))
	contextRow(&b, "WORKSPACE", orDash(m.surface.Workspace.Kind))
	contextRow(&b, "ROOT", truncate(orDash(m.surface.Workspace.Root), 25))
	contextRow(&b, "MODEL", truncate(orDash(m.status.Model), 25))
	contextRow(&b, "AUTH", orDash(m.status.AuthMode))
	contextRow(&b, "POLICY", orDash(m.surface.PermissionMode))
	contextRow(&b, "APPROVALS", fmt.Sprintf("%d", len(m.approvals)))
	if len(m.approvals) > 0 {
		b.WriteString("\n" + styleWarn.Render("DECISION REQUIRED"))
	}
	return panelStyle(contextSidebarWidth).Render(strings.TrimRight(b.String(), "\n"))
}

func contextRow(b *strings.Builder, label, value string) {
	b.WriteString(styleMuted.Render(label) + "\n")
	b.WriteString(styleVal.Render("  "+value) + "\n")
}

// composerSurface draws the single strong input surface: a full border that
// carries the active mode's color (yellow when blocked) around the textarea
// plus a MiMo-style mode/model status line, with a busy line replacing the
// input while a turn is in flight.
func (m model) composerSurface(width int, readiness executionReadiness) string {
	borderColor := m.mode.color()
	if !readiness.CanRun {
		borderColor = colWarn
	}
	border := lipgloss.RoundedBorder()
	if gl.ascii {
		border = asciiBorder
	}
	content := m.composer.View() + "\n" + m.modeStatusLine()
	if m.busy() {
		content = styleKey.Render(m.spinnerFrame()) + " " +
			styleMuted.Render("ATLAS is working "+gl.ellipsis+"  ctrl+c cancel")
	}
	return lipgloss.NewStyle().
		Width(max(30, width)).
		Padding(0, 1).
		Border(border).
		BorderForeground(borderColor).
		Render(content)
}

// modeStatusLine is the composer's identity row: active mode in its color,
// then auth mode / model, MiMo-style.
func (m model) modeStatusLine() string {
	mode := lipgloss.NewStyle().Foreground(m.mode.color()).Bold(true).Render(m.mode.label())
	meta := orDash(m.status.AuthMode) + " / " + orDash(m.status.Model)
	return mode + styleMuted.Render(" "+gl.bullet+" "+meta+"  "+m.mode.hint())
}

// commandMenuView renders the slash-command autocomplete under the composer.
func (m model) commandMenuView(width int) string {
	if !m.menuOpen() {
		return ""
	}
	var b strings.Builder
	for i, cmd := range m.menuMatches {
		name := fmt.Sprintf("%-14s", cmd.name)
		line := styleKey.Render(name) + styleMuted.Render(truncate(cmd.desc, max(10, width-16)))
		if i == m.menuIx {
			line = styleSelected.Render(">"+name) + " " + styleMuted.Render(truncate(cmd.desc, max(10, width-17)))
		} else {
			line = " " + line
		}
		b.WriteString(line + "\n")
	}
	b.WriteString(styleMuted.Render(" tab complete  enter run  esc dismiss"))
	return strings.TrimRight(b.String(), "\n")
}

// statusBar is the persistent bottom line: identity, connection, and key
// hints, truncated to terminal width.
func (m model) statusBar() string {
	hints := "enter send  alt+enter newline  tab mode  ctrl+p settings  ctrl+o context  / commands  ctrl+c cancel"
	if m.width > 0 && m.width < 100 {
		hints = "enter send | tab mode | ctrl+p settings | / commands | ctrl+c cancel"
	}
	return styleMuted.Render(truncate(hints, max(20, m.width-1)))
}

func (m model) chatFooter() string {
	return m.statusBar()
}
