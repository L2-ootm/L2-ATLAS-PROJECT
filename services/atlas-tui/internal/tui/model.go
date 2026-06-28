// Package tui is the ATLAS terminal workbench (BubbleTea).
//
// Reimplements opencode/MiMo terminal patterns ATLAS-native (no donor runtime
// imported). It is a thin client of the ATLAS gateway: it renders the provider
// mesh, missions, and a live run-event stream, and holds no business logic.
package tui

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"atlas-tui/internal/client"
)

type phase int

const (
	phaseLoading phase = iota
	phaseReady
)

// --- messages --------------------------------------------------------------

type statusMsg struct {
	status client.ProviderStatus
	err    error
}
type modesMsg struct {
	modes []client.ProviderMode
	err   error
}
type missionsMsg struct {
	missions []client.Mission
	err      error
}
type latestRunMsg struct {
	runID string
	err   error
}
type runEventMsg client.RunEvent
type streamDoneMsg struct{ err error }

// --- model -----------------------------------------------------------------

type model struct {
	c       *client.Client
	gateway string

	phase  phase
	status client.ProviderStatus
	modes  []client.ProviderMode

	missions []client.Mission
	cursor   int

	log       []string
	streaming bool
	streamRun string
	eventCh   chan client.RunEvent

	width, height int
	errMsg        string
}

// New builds the workbench model for a gateway base URL.
func New(c *client.Client, gateway string) model {
	return model{c: c, gateway: gateway, phase: phaseLoading}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(m.fetchStatus(), m.fetchModes(), m.fetchMissions())
}

// --- commands --------------------------------------------------------------

func (m model) fetchStatus() tea.Cmd {
	return func() tea.Msg {
		s, err := m.c.ProviderStatus(context.Background())
		return statusMsg{status: s, err: err}
	}
}

func (m model) fetchModes() tea.Cmd {
	return func() tea.Msg {
		mm, err := m.c.ProviderModes(context.Background())
		return modesMsg{modes: mm, err: err}
	}
}

func (m model) fetchMissions() tea.Cmd {
	return func() tea.Msg {
		ms, err := m.c.Missions(context.Background())
		return missionsMsg{missions: ms, err: err}
	}
}

func (m model) resolveLatestRun(missionID string) tea.Cmd {
	return func() tea.Msg {
		id, err := m.c.LatestRunID(context.Background(), missionID)
		return latestRunMsg{runID: id, err: err}
	}
}

func waitForEvent(ch chan client.RunEvent) tea.Cmd {
	return func() tea.Msg {
		ev, ok := <-ch
		if !ok {
			return streamDoneMsg{}
		}
		return runEventMsg(ev)
	}
}

// --- update ----------------------------------------------------------------

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height

	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit
		case "r":
			m.errMsg = ""
			return m, tea.Batch(m.fetchStatus(), m.fetchModes(), m.fetchMissions())
		case "j", "down":
			if m.cursor < len(m.missions)-1 {
				m.cursor++
			}
		case "k", "up":
			if m.cursor > 0 {
				m.cursor--
			}
		case "enter":
			if len(m.missions) > 0 && !m.streaming {
				m.appendLog(styleMuted.Render("resolving latest run..."))
				return m, m.resolveLatestRun(m.missions[m.cursor].ID)
			}
		}

	case statusMsg:
		m.phase = phaseReady
		if msg.err != nil {
			m.errMsg = "provider status: " + msg.err.Error()
		} else {
			m.status = msg.status
		}

	case modesMsg:
		if msg.err != nil {
			m.errMsg = "provider modes: " + msg.err.Error()
		} else {
			m.modes = msg.modes
		}

	case missionsMsg:
		if msg.err != nil {
			m.errMsg = "missions: " + msg.err.Error()
		} else {
			m.missions = msg.missions
			if m.cursor >= len(m.missions) {
				m.cursor = 0
			}
		}

	case latestRunMsg:
		if msg.err != nil {
			m.appendLog(styleBad.Render("run lookup failed: " + msg.err.Error()))
		} else if msg.runID == "" {
			m.appendLog(styleWarn.Render("no runs on this mission yet"))
		} else {
			m.streaming = true
			m.streamRun = msg.runID
			m.eventCh = make(chan client.RunEvent, 64)
			ch := m.eventCh
			runID := msg.runID
			c := m.c
			m.appendLog(styleGood.Render("streaming run " + short(runID) + " ..."))
			go func() {
				_ = c.StreamRun(context.Background(), runID, func(ev client.RunEvent) {
					ch <- ev
				})
				close(ch)
			}()
			return m, waitForEvent(ch)
		}

	case runEventMsg:
		m.appendLog(renderEvent(client.RunEvent(msg)))
		return m, waitForEvent(m.eventCh)

	case streamDoneMsg:
		m.streaming = false
		m.appendLog(styleMuted.Render("stream ended (" + short(m.streamRun) + ")"))
	}

	return m, nil
}

func (m *model) appendLog(line string) {
	m.log = append(m.log, line)
	if len(m.log) > 200 {
		m.log = m.log[len(m.log)-200:]
	}
}

// --- view ------------------------------------------------------------------

func (m model) View() string {
	if m.phase == phaseLoading {
		return "\n  " + styleMuted.Render("connecting to ATLAS gateway "+m.gateway+" ...")
	}
	var b strings.Builder
	b.WriteString(m.header() + "\n\n")
	b.WriteString(lipgloss.JoinHorizontal(lipgloss.Top, m.modesPanel(), "  ", m.missionsPanel()))
	b.WriteString("\n\n" + m.logPanel())
	b.WriteString("\n" + m.footer())
	return b.String()
}

func (m model) header() string {
	mode := styleGood.Render("live")
	if m.status.MockMode {
		mode = styleWarn.Render("MOCK MODE")
	}
	title := styleTitle.Render("ATLAS workbench")
	line := fmt.Sprintf("%s  %s  %s/%s  auth=%s  [%s]",
		title,
		styleMuted.Render(m.gateway),
		styleVal.Render(orDash(m.status.Provider)),
		styleVal.Render(orDash(m.status.Model)),
		styleKey.Render(orDash(m.status.AuthMode)),
		mode,
	)
	if m.errMsg != "" {
		line += "\n" + styleBad.Render("! "+m.errMsg)
	}
	return line
}

func (m model) modesPanel() string {
	var b strings.Builder
	b.WriteString(styleKey.Render("provider modes") + "\n")
	for _, md := range m.modes {
		mark := styleBad.Render("[--]")
		if md.Available {
			mark = styleGood.Render("[ok]")
		}
		active := ""
		if md.Active {
			active = styleViolet(" <- active")
		}
		b.WriteString(fmt.Sprintf("%s %-13s%s\n", mark, md.Mode, active))
	}
	if len(m.modes) == 0 {
		b.WriteString(styleMuted.Render("(none)\n"))
	}
	return stylePanel.Width(34).Render(strings.TrimRight(b.String(), "\n"))
}

func (m model) missionsPanel() string {
	var b strings.Builder
	b.WriteString(styleKey.Render("missions") + "\n")
	if len(m.missions) == 0 {
		b.WriteString(styleMuted.Render("(none)"))
	}
	for i, ms := range m.missions {
		if i >= 8 {
			b.WriteString(styleMuted.Render(fmt.Sprintf("… +%d more", len(m.missions)-8)))
			break
		}
		row := fmt.Sprintf("%-8s %s", ms.Status, truncate(ms.Title, 28))
		if i == m.cursor {
			row = styleSelected.Render("> " + row)
		} else {
			row = "  " + styleVal.Render(row)
		}
		b.WriteString(row + "\n")
	}
	return stylePanel.Width(44).Render(strings.TrimRight(b.String(), "\n"))
}

func (m model) logPanel() string {
	title := styleKey.Render("run stream")
	if m.streaming {
		title += styleGood.Render(" ● live")
	}
	tail := m.log
	if len(tail) > 8 {
		tail = tail[len(tail)-8:]
	}
	body := strings.Join(tail, "\n")
	if body == "" {
		body = styleMuted.Render("select a mission and press enter to stream its latest run")
	}
	return title + "\n" + stylePanel.Width(80).Render(body)
}

func (m model) footer() string {
	return styleMuted.Render("j/k move · enter stream · r refresh · q quit")
}

// --- helpers ---------------------------------------------------------------

func renderEvent(ev client.RunEvent) string {
	switch ev.Name {
	case "end":
		var d struct {
			Status string `json:"status"`
		}
		_ = json.Unmarshal(ev.Data, &d)
		return styleMuted.Render("— run " + orDash(d.Status) + " —")
	case "stream_error":
		return styleBad.Render("stream error: " + string(ev.Data))
	default: // "audit"
		var d struct {
			EventType string `json:"event_type"`
			ToolName  string `json:"tool_name"`
		}
		_ = json.Unmarshal(ev.Data, &d)
		label := d.EventType
		if d.ToolName != "" {
			label += " " + d.ToolName
		}
		return styleVal.Render("• " + orDash(label))
	}
}

func styleViolet(s string) string {
	return lipgloss.NewStyle().Foreground(colViolet).Render(s)
}

func orDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}

func short(s string) string {
	if len(s) > 8 {
		return s[:8]
	}
	return s
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	if n <= 1 {
		return s[:n]
	}
	return s[:n-1] + "…"
}
