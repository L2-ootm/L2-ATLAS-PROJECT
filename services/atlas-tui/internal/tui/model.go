// Package tui is the ATLAS terminal workbench (BubbleTea).
//
// Reimplements opencode/MiMo terminal patterns ATLAS-native (no donor runtime
// imported). It is a thin client of the ATLAS gateway: it renders the provider
// mesh, missions, a live run-event stream, the tool-approval queue, and a
// composer that submits a mission + drives a real run end-to-end. It holds no
// business logic — render + input + HTTP only (D-022).
package tui

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"atlas-tui/internal/client"
)

type phase int

const (
	phaseLoading phase = iota
	phaseReady
)

// focus is the active input region. Keys route by focus so the composer can
// own raw text while the panes keep single-key navigation.
type focus int

const (
	focusMissions focus = iota
	focusPermissions
	focusComposer
)

const approvalPollInterval = 4 * time.Second

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
type approvalsMsg struct {
	approvals []client.ToolApproval
	err       error
}
type approvalActionMsg struct {
	verb     string // "approved" | "rejected"
	approval client.ToolApproval
	err      error
}
type pollTickMsg struct{}
type latestRunMsg struct {
	runID string
	err   error
}
type missionCreatedMsg struct {
	mission client.Mission
	err     error
}
type runStartedMsg struct {
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
	focus  focus
	status client.ProviderStatus
	modes  []client.ProviderMode

	missions []client.Mission
	cursor   int

	approvals  []client.ToolApproval
	approvalIx int

	log       []string
	viewport  viewport.Model
	vpReady   bool
	streaming bool
	streamRun string
	eventCh   chan client.RunEvent

	composer   textarea.Model
	submitting bool

	width, height int
	errMsg        string
}

// New builds the workbench model for a gateway base URL.
func New(c *client.Client, gateway string) model {
	ta := textarea.New()
	ta.Placeholder = "Describe a mission, then ctrl+s to run it" + gl.ellipsis
	ta.Prompt = styleVioletStyle.Render(gl.prompt)
	ta.CharLimit = 4000
	ta.ShowLineNumbers = false
	ta.SetHeight(3)
	return model{
		c:        c,
		gateway:  gateway,
		phase:    phaseLoading,
		focus:    focusMissions,
		composer: ta,
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(m.fetchStatus(), m.fetchModes(), m.fetchMissions(), m.fetchApprovals(), schedulePoll())
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

func (m model) fetchApprovals() tea.Cmd {
	return func() tea.Msg {
		as, err := m.c.ToolApprovals(context.Background(), "pending")
		return approvalsMsg{approvals: as, err: err}
	}
}

func schedulePoll() tea.Cmd {
	return tea.Tick(approvalPollInterval, func(time.Time) tea.Msg { return pollTickMsg{} })
}

func (m model) resolveLatestRun(missionID string) tea.Cmd {
	return func() tea.Msg {
		id, err := m.c.LatestRunID(context.Background(), missionID)
		return latestRunMsg{runID: id, err: err}
	}
}

func (m model) submitMission(title, intent string) tea.Cmd {
	return func() tea.Msg {
		ms, err := m.c.CreateMission(context.Background(), title, intent)
		return missionCreatedMsg{mission: ms, err: err}
	}
}

func (m model) startRun(missionID string) tea.Cmd {
	return func() tea.Msg {
		id, err := m.c.StartRun(context.Background(), missionID, "native", true)
		return runStartedMsg{runID: id, err: err}
	}
}

func (m model) approveTool(id string) tea.Cmd {
	return func() tea.Msg {
		a, err := m.c.ApproveTool(context.Background(), id)
		return approvalActionMsg{verb: "approved", approval: a, err: err}
	}
}

func (m model) rejectTool(id string) tea.Cmd {
	return func() tea.Msg {
		a, err := m.c.RejectTool(context.Background(), id, "rejected from atlas-tui")
		return approvalActionMsg{verb: "rejected", approval: a, err: err}
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
		m.layout()
		return m, nil

	case tea.KeyMsg:
		return m.handleKey(msg)

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

	case approvalsMsg:
		if msg.err != nil {
			m.errMsg = "approvals: " + msg.err.Error()
		} else {
			m.approvals = msg.approvals
			if m.approvalIx >= len(m.approvals) {
				m.approvalIx = 0
			}
		}

	case pollTickMsg:
		return m, tea.Batch(m.fetchApprovals(), schedulePoll())

	case approvalActionMsg:
		if msg.err != nil {
			m.appendLog(styleBad.Render("approval " + msg.verb + " failed: " + msg.err.Error()))
		} else {
			m.appendLog(styleGood.Render(fmt.Sprintf("%s %s [%s]", msg.verb, msg.approval.ToolName, msg.approval.Status)))
		}
		return m, m.fetchApprovals()

	case missionCreatedMsg:
		if msg.err != nil {
			m.submitting = false
			m.appendLog(styleBad.Render("mission create failed: " + msg.err.Error()))
		} else {
			m.appendLog(styleGood.Render("mission created " + short(msg.mission.ID) + " " + gl.dash + " starting run" + gl.ellipsis))
			return m, tea.Batch(m.fetchMissions(), m.startRun(msg.mission.ID))
		}

	case runStartedMsg:
		m.submitting = false
		if msg.err != nil {
			m.appendLog(styleBad.Render("run start failed: " + msg.err.Error()))
		} else {
			return m.beginStream(msg.runID)
		}

	case latestRunMsg:
		if msg.err != nil {
			m.appendLog(styleBad.Render("run lookup failed: " + msg.err.Error()))
		} else if msg.runID == "" {
			m.appendLog(styleWarn.Render("no runs on this mission yet"))
		} else {
			return m.beginStream(msg.runID)
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

// beginStream wires the SSE consumer for a run id and starts pumping events.
func (m model) beginStream(runID string) (tea.Model, tea.Cmd) {
	m.streaming = true
	m.streamRun = runID
	m.eventCh = make(chan client.RunEvent, 64)
	ch := m.eventCh
	c := m.c
	m.appendLog(styleGood.Render("streaming run " + short(runID) + " " + gl.ellipsis))
	go func() {
		_ = c.StreamRun(context.Background(), runID, func(ev client.RunEvent) {
			ch <- ev
		})
		close(ch)
	}()
	return m, waitForEvent(ch)
}

func (m model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	// Composer owns most keys while focused; only the explicit verbs escape it.
	if m.focus == focusComposer {
		switch msg.String() {
		case "ctrl+c":
			return m, tea.Quit
		case "esc":
			m.composer.Blur()
			m.focus = focusMissions
			return m, nil
		case "ctrl+s":
			return m.submitComposer()
		}
		var cmd tea.Cmd
		m.composer, cmd = m.composer.Update(msg)
		return m, cmd
	}

	switch msg.String() {
	case "q", "ctrl+c":
		return m, tea.Quit
	case "r":
		m.errMsg = ""
		return m, tea.Batch(m.fetchStatus(), m.fetchModes(), m.fetchMissions(), m.fetchApprovals())
	case "tab":
		m.focus = (m.focus + 1) % 2 // cycle missions <-> permissions
		return m, nil
	case "n":
		m.focus = focusComposer
		m.composer.Focus()
		return m, textarea.Blink
	case "p":
		m.focus = focusPermissions
		return m, nil
	case "m":
		m.focus = focusMissions
		return m, nil
	}

	switch m.focus {
	case focusMissions:
		return m.handleMissionsKey(msg)
	case focusPermissions:
		return m.handlePermissionsKey(msg)
	}
	return m, nil
}

func (m model) handleMissionsKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
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
			m.appendLog(styleMuted.Render("resolving latest run" + gl.ellipsis))
			return m, m.resolveLatestRun(m.missions[m.cursor].ID)
		}
	}
	return m, nil
}

func (m model) handlePermissionsKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "j", "down":
		if m.approvalIx < len(m.approvals)-1 {
			m.approvalIx++
		}
	case "k", "up":
		if m.approvalIx > 0 {
			m.approvalIx--
		}
	case "a", "enter":
		if m.approvalIx < len(m.approvals) {
			return m, m.approveTool(m.approvals[m.approvalIx].ID)
		}
	case "x":
		if m.approvalIx < len(m.approvals) {
			return m, m.rejectTool(m.approvals[m.approvalIx].ID)
		}
	}
	return m, nil
}

// submitComposer turns the composer text into a mission + executed run.
func (m model) submitComposer() (tea.Model, tea.Cmd) {
	text := strings.TrimSpace(m.composer.Value())
	if text == "" {
		return m, nil
	}
	title := firstLine(text)
	m.composer.Reset()
	m.composer.Blur()
	m.focus = focusMissions
	m.submitting = true
	m.appendLog(styleKey.Render("» submitting mission: ") + styleVal.Render(truncate(title, 60)))
	return m, m.submitMission(truncate(title, 120), text)
}

func (m *model) appendLog(line string) {
	m.log = append(m.log, line)
	if len(m.log) > 500 {
		m.log = m.log[len(m.log)-500:]
	}
	if m.vpReady {
		m.viewport.SetContent(strings.Join(m.log, "\n"))
		m.viewport.GotoBottom()
	}
}

// layout sizes the scrollback viewport from the current terminal dimensions.
func (m *model) layout() {
	// Reserve rows for header(3) + panels(11) + composer(5) + footer(2).
	h := m.height - 21
	if h < 4 {
		h = 4
	}
	w := m.width - 2
	if w < 20 {
		w = 20
	}
	if !m.vpReady {
		m.viewport = viewport.New(w, h)
		m.vpReady = true
	} else {
		m.viewport.Width = w
		m.viewport.Height = h
	}
	m.viewport.SetContent(strings.Join(m.log, "\n"))
	m.viewport.GotoBottom()
	m.composer.SetWidth(w)
}

// --- view ------------------------------------------------------------------

func (m model) View() string {
	if m.phase == phaseLoading {
		return "\n  " + styleMuted.Render("connecting to ATLAS gateway "+m.gateway+" "+gl.ellipsis)
	}
	var b strings.Builder
	b.WriteString(m.header() + "\n\n")
	b.WriteString(lipgloss.JoinHorizontal(lipgloss.Top, m.modesPanel(), "  ", m.missionsPanel(), "  ", m.permissionsPanel()))
	b.WriteString("\n\n" + m.logPanel())
	b.WriteString("\n" + m.composerPanel())
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
	return stylePanel.Width(30).Render(strings.TrimRight(b.String(), "\n"))
}

func (m model) missionsPanel() string {
	var b strings.Builder
	b.WriteString(paneTitle("missions", m.focus == focusMissions) + "\n")
	if len(m.missions) == 0 {
		b.WriteString(styleMuted.Render("(none)"))
	}
	for i, ms := range m.missions {
		if i >= 8 {
			b.WriteString(styleMuted.Render(fmt.Sprintf("%s +%d more", gl.ellipsis, len(m.missions)-8)))
			break
		}
		row := fmt.Sprintf("%-8s %s", ms.Status, truncate(ms.Title, 24))
		if i == m.cursor && m.focus == focusMissions {
			row = styleSelected.Render("> " + row)
		} else {
			row = "  " + styleVal.Render(row)
		}
		b.WriteString(row + "\n")
	}
	return stylePanel.Width(40).Render(strings.TrimRight(b.String(), "\n"))
}

func (m model) permissionsPanel() string {
	var b strings.Builder
	hdr := paneTitle("permissions", m.focus == focusPermissions)
	if len(m.approvals) > 0 {
		hdr += styleWarn.Render(fmt.Sprintf(" (%d)", len(m.approvals)))
	}
	b.WriteString(hdr + "\n")
	if len(m.approvals) == 0 {
		b.WriteString(styleMuted.Render("no pending approvals"))
	}
	for i, a := range m.approvals {
		if i >= 8 {
			b.WriteString(styleMuted.Render(fmt.Sprintf("%s +%d more", gl.ellipsis, len(m.approvals)-8)))
			break
		}
		label := fmt.Sprintf("%-5s %s", riskTag(a.RiskLevel), truncate(approvalLabel(a), 26))
		if i == m.approvalIx && m.focus == focusPermissions {
			label = styleSelected.Render("> " + label)
		} else {
			label = "  " + styleVal.Render(label)
		}
		b.WriteString(label + "\n")
	}
	return stylePanel.Width(40).Render(strings.TrimRight(b.String(), "\n"))
}

func (m model) logPanel() string {
	title := styleKey.Render("run stream")
	if m.streaming {
		title += styleGood.Render(" " + gl.live + " live")
	} else if m.submitting {
		title += styleWarn.Render(" " + gl.ellipsis + " submitting")
	}
	body := m.viewport.View()
	if !m.vpReady {
		body = stylePanel.Render(styleMuted.Render("select a mission and press enter, or n to compose a new one"))
	}
	return title + "\n" + body
}

func (m model) composerPanel() string {
	if m.focus == focusComposer {
		return styleKey.Render("compose mission") + styleMuted.Render("  ctrl+s run · esc cancel") + "\n" + m.composer.View()
	}
	return styleMuted.Render("n compose new mission")
}

func (m model) footer() string {
	switch m.focus {
	case focusComposer:
		return styleMuted.Render("ctrl+s run · esc cancel · ctrl+c quit")
	case focusPermissions:
		return styleMuted.Render("j/k move · a/enter approve · x reject · tab missions · n compose · r refresh · q quit")
	default:
		return styleMuted.Render("j/k move · enter stream · tab permissions · n compose · p perms · r refresh · q quit")
	}
}

// --- helpers ---------------------------------------------------------------

func renderEvent(ev client.RunEvent) string {
	switch ev.Name {
	case "end":
		var d struct {
			Status string `json:"status"`
		}
		_ = json.Unmarshal(ev.Data, &d)
		return styleMuted.Render(gl.dash + " run " + orDash(d.Status) + " " + gl.dash)
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
		return styleVal.Render(gl.bullet + " " + orDash(label))
	}
}

func paneTitle(name string, active bool) string {
	if active {
		return styleVioletStyle.Bold(true).Render(gl.paneBar + name)
	}
	return styleKey.Render(" " + name)
}

func riskTag(level string) string {
	switch level {
	case "high", "critical":
		return styleBad.Render(strings.ToUpper(level[:min(4, len(level))]))
	case "medium":
		return styleWarn.Render("MED")
	default:
		return styleMuted.Render("LOW")
	}
}

func approvalLabel(a client.ToolApproval) string {
	if a.Summary != "" {
		return a.Summary
	}
	return a.ToolName
}

func firstLine(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return strings.TrimSpace(s[:i])
	}
	return strings.TrimSpace(s)
}

func styleViolet(s string) string {
	return styleVioletStyle.Render(s)
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
	return s[:n-1] + gl.ellipsis
}
