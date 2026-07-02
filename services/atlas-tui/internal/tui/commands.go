package tui

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

func (m model) executeSlashCommand(input string) (bool, model, tea.Cmd) {
	fields := strings.Fields(strings.TrimSpace(input))
	if len(fields) == 0 || !strings.HasPrefix(fields[0], "/") {
		return false, m, nil
	}
	switch strings.ToLower(fields[0]) {
	case "/settings", "/provider":
		m.focus = focusSettings
		m.settingsLoading = true
		m.settings = nil
		m.errMsg = ""
		return true, m, m.fetchSettings()
	case "/sidebar", "/context":
		m.showSidebar = !m.showSidebar
		m.layout()
		return true, m, nil
	case "/permissions":
		if len(m.approvals) == 0 {
			m.appendLog(styleHUD.Render("SYSTEM") + "  " + styleMuted.Render("No owned approvals pending."))
		} else {
			m.overlay = newApprovalOverlay(m.approvals[m.approvalIx])
		}
		return true, m, nil
	case "/missions", "/history":
		if len(m.missions) == 0 {
			m.appendLog(styleHUD.Render("SYSTEM") + "  " + styleMuted.Render("No mission history recorded."))
			return true, m, nil
		}
		limit := min(5, len(m.missions))
		rows := make([]string, 0, limit)
		for _, mission := range m.missions[:limit] {
			rows = append(rows, fmt.Sprintf("%s %s", mission.Status, mission.Title))
		}
		m.appendLog(styleHUD.Render("HISTORY") + "  " + styleMuted.Render(strings.Join(rows, " | ")))
		return true, m, nil
	case "/new":
		m.log = nil
		m.lastSurfaceSeq = -1
		if m.vpReady {
			m.viewport.SetContent("")
		}
		m.errMsg = ""
		return true, m, nil
	case "/help", "/commands":
		m.appendLog(styleHUD.Render("COMMANDS") + "  " + styleMuted.Render(
			"/settings  /missions  /permissions  /sidebar  /new  /quit",
		))
		return true, m, nil
	case "/quit", "/exit":
		if m.surface.ID == "" || m.surface.OwnerToken == "" {
			return true, m, tea.Quit
		}
		return true, m, tea.Sequence(m.closeSurface(), tea.Quit)
	default:
		m.appendLog(styleHUD.Render("SYSTEM") + "  " + styleBad.Render(
			"Unknown command. Use /help.",
		))
		return true, m, nil
	}
}
