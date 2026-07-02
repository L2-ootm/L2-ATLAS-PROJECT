package tui

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"atlas-tui/internal/client"
)

// slashCommand is one entry in the operator command registry. Aliases resolve
// in executeSlashCommand; the menu lists primaries only.
type slashCommand struct {
	name string
	desc string
}

var slashCommands = []slashCommand{
	{"/settings", "provider, model, and auth configuration"},
	{"/permissions", "review owned pending approvals"},
	{"/history", "recent missions on this gateway"},
	{"/sidebar", "toggle the context sidebar"},
	{"/new", "clear the visible conversation"},
	{"/help", "list commands"},
	{"/quit", "close the session and exit"},
}

// commandMatches returns registry entries whose name starts with the typed
// prefix. A bare "/" lists everything.
func commandMatches(input string) []slashCommand {
	input = strings.ToLower(strings.TrimSpace(input))
	if input == "" || !strings.HasPrefix(input, "/") || strings.ContainsAny(input, " \n") {
		return nil
	}
	var out []slashCommand
	for _, cmd := range slashCommands {
		if strings.HasPrefix(cmd.name, input) {
			out = append(out, cmd)
		}
	}
	return out
}

// syncMenu recomputes the autocomplete menu from the composer text.
func (m *model) syncMenu() {
	m.menuMatches = commandMatches(m.composer.Value())
	if m.menuIx >= len(m.menuMatches) {
		m.menuIx = 0
	}
}

func (m model) menuOpen() bool {
	return len(m.menuMatches) > 0
}

// handleMenuKey owns navigation keys while the command menu is visible.
// Unhandled keys fall through to the composer.
func (m model) handleMenuKey(msg tea.KeyMsg) (bool, tea.Model, tea.Cmd) {
	switch msg.String() {
	case "up", "ctrl+k":
		if m.menuIx > 0 {
			m.menuIx--
		}
		return true, m, nil
	case "down", "ctrl+j":
		if m.menuIx < len(m.menuMatches)-1 {
			m.menuIx++
		}
		return true, m, nil
	case "tab":
		m.composer.SetValue(m.menuMatches[m.menuIx].name)
		m.composer.CursorEnd()
		m.syncMenu()
		return true, m, nil
	case "enter":
		selected := m.menuMatches[m.menuIx].name
		m.menuMatches = nil
		if handled, updated, cmd := m.executeSlashCommand(selected); handled {
			updated.composer.Reset()
			if updated.focus == focusComposer {
				updated.composer.Focus()
			}
			return true, updated, cmd
		}
		return true, m, nil
	case "esc":
		m.menuMatches = nil
		return true, m, nil
	}
	return false, m, nil
}

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
			m.appendSystem("No owned approvals pending.")
		} else {
			m.overlay = newApprovalOverlay(m.approvals[m.approvalIx])
		}
		return true, m, nil
	case "/missions", "/history":
		if len(m.missions) == 0 {
			m.appendSystem("No mission history recorded.")
			return true, m, nil
		}
		limit := min(5, len(m.missions))
		rows := make([]string, 0, limit)
		for _, mission := range m.missions[:limit] {
			rows = append(rows, fmt.Sprintf("%s %s", mission.Status, mission.Title))
		}
		m.appendSystem("HISTORY  " + strings.Join(rows, " | "))
		return true, m, nil
	case "/new":
		m.items = nil
		m.lastAssistantText = ""
		if m.vpReady {
			m.viewport.SetContent("")
		}
		m.errMsg = ""
		return true, m, nil
	case "/help", "/commands":
		var names []string
		for _, cmd := range slashCommands {
			names = append(names, cmd.name)
		}
		m.appendSystem("COMMANDS  " + strings.Join(names, "  "))
		return true, m, nil
	case "/quit", "/exit":
		if m.surface.ID == "" || m.surface.OwnerToken == "" {
			return true, m, tea.Quit
		}
		return true, m, tea.Sequence(m.closeSurface(), tea.Quit)
	default:
		m.appendItem(transcriptItem{
			kind: itemError, label: "command", text: "Unknown command. Use /help.",
		})
		return true, m, nil
	}
}

func approvalLabel(a client.ToolApproval) string {
	if a.Summary != "" {
		return a.Summary
	}
	return a.ToolName
}
