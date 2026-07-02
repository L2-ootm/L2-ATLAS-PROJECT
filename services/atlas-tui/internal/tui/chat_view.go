package tui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

const contextSidebarWidth = 32

func (m model) chatView() string {
	if len(m.log) == 0 && !m.submitting && !m.streaming {
		return m.idleChatView()
	}
	return m.activeChatView()
}

func (m model) idleChatView() string {
	width := max(40, m.width)
	height := max(18, m.height-2)
	cardWidth := min(84, max(48, width-12))
	readiness := readinessFor(m.status, mockAllowed())

	var body strings.Builder
	body.WriteString(styleTitle.Bold(true).Render("L2 // ATLAS"))
	body.WriteString("\n" + styleHUD.Render("AGENT WORKBENCH"))
	body.WriteString("\n\n")
	body.WriteString(styleMuted.Render("MESSAGE ATLAS"))
	body.WriteString("\n")
	body.WriteString(composerSurface(m.composer.View(), cardWidth, readiness))
	body.WriteString("\n")
	if readiness.CanRun {
		body.WriteString(styleVal.Render(readinessLine(m)))
		body.WriteString("\n")
		body.WriteString(styleMuted.Render("enter submit  alt+enter newline  ctrl+p settings  / commands"))
	} else {
		body.WriteString(onboardingNotice(m))
	}
	if m.errMsg != "" {
		body.WriteString("\n\n" + styleBad.Render(m.errMsg))
	}
	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, body.String())
}

func onboardingNotice(m model) string {
	var b strings.Builder
	b.WriteString(styleWarn.Render("CONFIGURE PROVIDER") + "\n")
	for _, mode := range m.modes {
		label := strings.ToUpper(strings.TrimSpace(mode.Label))
		if label == "" {
			label = strings.ToUpper(strings.ReplaceAll(mode.Mode, "_", " "))
		}
		state := "MISSING"
		if mode.Available {
			state = "READY"
		}
		if mode.Active {
			state = "ACTIVE / " + state
		}
		b.WriteString(styleMuted.Render(fmt.Sprintf("%-18s %s", label, state)) + "\n")
	}
	b.WriteString(styleVal.Render("ctrl+p configure") + styleMuted.Render("  mock requires ATLAS_TUI_ALLOW_MOCK=1"))
	return strings.TrimRight(b.String(), "\n")
}

func (m model) activeChatView() string {
	header := m.compactHeader()
	transcript := m.transcriptView()
	composer := styleMuted.Render("MESSAGE ATLAS") + "\n" +
		composerSurface(m.composer.View(), max(30, m.viewport.Width), readinessFor(m.status, mockAllowed()))
	main := strings.Join([]string{header, "", transcript, "", composer}, "\n")
	if m.showSidebar && m.width >= 110 {
		main = lipgloss.JoinHorizontal(
			lipgloss.Top,
			lipgloss.NewStyle().Width(max(40, m.width-contextSidebarWidth-4)).Render(main),
			"  ",
			m.contextSidebar(),
		)
	}
	return main + "\n" + m.chatFooter()
}

func (m model) chatOverlayView() string {
	var b strings.Builder
	b.WriteString(m.compactHeader() + "\n\n")
	b.WriteString(styleHUD.Render("TRANSCRIPT") + "\n")
	start := max(0, len(m.log)-5)
	for _, line := range m.log[start:] {
		b.WriteString(line + "\n")
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
	if m.streaming {
		line += "  " + styleBlue("STREAMING")
	}
	if m.errMsg != "" {
		line += "\n" + styleBad.Render(m.errMsg)
	}
	return line
}

func (m model) transcriptView() string {
	title := styleHUD.Render("TRANSCRIPT")
	if m.streaming {
		title += "  " + styleBlue(gl.live+" LIVE")
	} else if m.submitting {
		title += "  " + styleWarn.Render("DISPATCHING")
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

func composerSurface(content string, width int, readiness executionReadiness) string {
	borderColor := colViolet
	if !readiness.CanRun {
		borderColor = colWarn
	}
	border := lipgloss.NormalBorder()
	if gl.ascii {
		border = asciiBorder
	}
	return lipgloss.NewStyle().
		Width(max(30, width)).
		Padding(0, 1).
		Border(border).
		BorderLeft(true).
		BorderRight(false).
		BorderTop(false).
		BorderBottom(false).
		BorderForeground(borderColor).
		Render(content)
}

func readinessLine(m model) string {
	readiness := readinessFor(m.status, mockAllowed())
	return fmt.Sprintf("%s  %s / %s  %s",
		readiness.Label,
		orDash(m.status.AuthMode),
		orDash(m.status.Model),
		orDash(m.surface.PermissionMode),
	)
}

func (m model) chatFooter() string {
	if m.width > 0 && m.width < 100 {
		return styleMuted.Render("enter send | alt+enter newline | ctrl+p settings | ctrl+c cancel")
	}
	return styleMuted.Render("enter send  alt+enter newline  ctrl+p settings  ctrl+o context  / commands  ctrl+c cancel")
}

func renderUserTurn(text string) string {
	return styleHUD.Render("YOU") + "  " + styleVal.Render(strings.TrimSpace(text))
}

func styleBlue(value string) string {
	return styleKey.Render(value)
}
