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
	{"/mode", "switch agent mode: build, plan, or compose"},
	{"/dream", "consolidate project memory into durable wiki knowledge"},
	{"/distill", "mine recent work for reusable workflows and skills"},
	{"/deep-research", "deep multi-source research brief on a topic"},
	{"/review", "review uncommitted changes in the workspace"},
	{"/freellmapi", "control the free endpoint sidecar: status, start, stop"},
	{"/permissions", "review owned pending approvals"},
	{"/history", "recent missions on this gateway"},
	{"/sidebar", "toggle the context sidebar"},
	{"/new", "clear the visible conversation"},
	{"/help", "list commands"},
	{"/quit", "close the session and exit"},
}

// formatMissionRow renders one /missions history row with the same information
// density as the cockpit mission list: status, title, truncated intent, and
// the updated_at day (mission timestamps are RFC3339; the date part suffices
// in a one-line row).
func formatMissionRow(mission client.Mission) string {
	row := fmt.Sprintf("%s %s", mission.Status, mission.Title)
	if intent := strings.TrimSpace(mission.Intent); intent != "" && intent != mission.Title {
		if len(intent) > 40 {
			intent = intent[:37] + "..."
		}
		row += " — " + intent
	}
	if len(mission.UpdatedAt) >= 10 {
		row += " (" + mission.UpdatedAt[:10] + ")"
	}
	return row
}

// builtinWorkflow is a MiMo-style named workflow shipped as a first-class
// slash command: a curated intent template dispatched as a real mission.
type builtinWorkflow struct {
	title    string
	usage    string
	needArgs bool
	intent   func(args string) string
}

var builtinWorkflows = map[string]builtinWorkflow{
	"/dream": {
		title: "Dream: consolidate project memory",
		intent: func(string) string {
			return "DREAM — consolidate project memory. Review recent missions, runs, " +
				"observations, and wiki entries; distill durable knowledge, decisions, and " +
				"gotchas; propose (and where the permission broker allows, draft) wiki " +
				"updates capturing them. Report what was consolidated and what was skipped."
		},
	},
	"/distill": {
		title: "Distill: package repeated workflows",
		intent: func(string) string {
			return "DISTILL — analyze recent missions and runs for repeated workflows or " +
				"patterns. Package each as a reusable proposal: name, trigger, steps, " +
				"expected output, and whether it fits a skill, command, or checklist. " +
				"Report the top 3 candidates ranked by leverage."
		},
	},
	"/deep-research": {
		title:    "Deep research",
		usage:    "/deep-research <topic>",
		needArgs: true,
		intent: func(args string) string {
			return "DEEP RESEARCH — produce a structured, fact-checked research brief on: " +
				args + "\n\nSections: landscape overview, key options with tradeoffs, risks " +
				"and unknowns, recommendation, and what to verify next. Cite sources where " +
				"possible and mark unverified claims explicitly."
		},
	},
	"/review": {
		title: "Review workspace changes",
		intent: func(args string) string {
			scope := strings.TrimSpace(args)
			if scope == "" {
				scope = "the uncommitted changes"
			}
			return "REVIEW — review " + scope + " in this workspace: correctness bugs, " +
				"risky edge cases, security issues, and simplification opportunities. Be " +
				"specific with file and line references and rank findings by severity."
		},
	},
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
	name := strings.ToLower(fields[0])
	if wf, ok := builtinWorkflows[name]; ok {
		args := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(input), fields[0]))
		if wf.needArgs && args == "" {
			m.appendSystem("usage: " + wf.usage)
			return true, m, nil
		}
		updated, cmd := m.dispatchMission(wf.title, wf.intent(args), strings.TrimSpace(input))
		return true, updated, cmd
	}
	switch name {
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
	case "/mode":
		if len(fields) > 1 {
			mode, ok := modeByName(strings.ToLower(fields[1]))
			if !ok {
				m.appendSystem("usage: /mode build|plan|compose (or tab to cycle)")
				return true, m, nil
			}
			m.mode = mode
		} else {
			m.mode = m.mode.next()
		}
		m.appendSystem("MODE " + m.mode.label() + "  " + gl.bullet + "  " + m.mode.hint())
		return true, m, nil
	case "/freellmapi":
		verb := "status"
		if len(fields) > 1 {
			verb = strings.ToLower(fields[1])
		}
		if verb != "status" && verb != "start" && verb != "stop" {
			m.appendSystem("usage: /freellmapi [status|start|stop]")
			return true, m, nil
		}
		return true, m, m.freellmapiAction(verb)
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
			rows = append(rows, formatMissionRow(mission))
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
