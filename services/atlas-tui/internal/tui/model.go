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
	focusSettings
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
type surfaceCreatedMsg struct {
	session client.SurfaceSession
	err     error
}
type surfaceLifecycleMsg struct {
	action  string
	session client.SurfaceSession
	err     error
}
type surfaceEventsMsg struct {
	replay client.SurfaceEventReplay
	err    error
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

	phase          phase
	focus          focus
	status         client.ProviderStatus
	modes          []client.ProviderMode
	surface        client.SurfaceSession
	lastSurfaceSeq int64
	overlay        *overlayModel

	missions []client.Mission
	cursor   int

	approvals  []client.ToolApproval
	approvalIx int

	log             []string
	viewport        viewport.Model
	vpReady         bool
	streaming       bool
	streamRun       string
	eventCh         chan client.RunEvent
	cancelRequested bool

	composer   textarea.Model
	submitting bool

	settings        *settingsForm
	settingsLoading bool
	probing         bool
	probeMissionID  string
	probeOutcome    string

	width, height int
	errMsg        string
	showSidebar   bool
}

// New builds the workbench model for a gateway base URL.
func New(c *client.Client, gateway string) model {
	ta := textarea.New()
	ta.Placeholder = "Type your message" + gl.ellipsis
	ta.Prompt = " "
	ta.CharLimit = 4000
	ta.ShowLineNumbers = false
	ta.SetHeight(3)
	ta.Focus()
	return model{
		c:              c,
		gateway:        gateway,
		phase:          phaseLoading,
		focus:          focusComposer,
		composer:       ta,
		lastSurfaceSeq: -1,
		showSidebar:    true,
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(m.fetchStatus(), m.fetchModes(), m.fetchMissions(), m.createSurface())
}

// --- commands --------------------------------------------------------------

func (m model) createSurface() tea.Cmd {
	return func() tea.Msg {
		session, err := m.c.CreateSurface(context.Background(), "tui", "global", "")
		return surfaceCreatedMsg{session: session, err: err}
	}
}

func (m model) heartbeatSurface() tea.Cmd {
	return func() tea.Msg {
		session, err := m.c.HeartbeatSurface(context.Background(), m.surface)
		return surfaceLifecycleMsg{action: "heartbeat", session: session, err: err}
	}
}

func (m model) closeSurface() tea.Cmd {
	return func() tea.Msg {
		session, err := m.c.CloseSurface(context.Background(), m.surface)
		return surfaceLifecycleMsg{action: "close", session: session, err: err}
	}
}

func (m model) cancelSurface() tea.Cmd {
	return func() tea.Msg {
		session, err := m.c.CancelSurface(context.Background(), m.surface)
		return surfaceLifecycleMsg{action: "cancel", session: session, err: err}
	}
}

func (m model) fetchSurfaceEvents() tea.Cmd {
	return func() tea.Msg {
		replay, err := m.c.SurfaceEvents(
			context.Background(),
			m.surface,
			m.lastSurfaceSeq,
		)
		return surfaceEventsMsg{replay: replay, err: err}
	}
}

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
		as, err := m.c.ToolApprovals(context.Background(), "pending", m.surface)
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
		id, err := m.c.StartRun(
			context.Background(),
			missionID,
			m.selectedAgent(),
			true,
			m.surface.ID,
		)
		return runStartedMsg{runID: id, err: err}
	}
}

func (m model) selectedAgent() string {
	if m.status.AuthMode == "claude_code" {
		return "claude_code"
	}
	return "native"
}

func (m model) approveTool(approval client.ToolApproval, scope string) tea.Cmd {
	return func() tea.Msg {
		a, err := m.c.ApproveTool(context.Background(), m.surface, approval, scope)
		return approvalActionMsg{verb: "approved", approval: a, err: err}
	}
}

func (m model) rejectTool(approval client.ToolApproval) tea.Cmd {
	return func() tea.Msg {
		a, err := m.c.RejectTool(
			context.Background(), m.surface, approval, "rejected from atlas-tui",
		)
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

	case surfaceCreatedMsg:
		if msg.err != nil {
			m.errMsg = surfaceError("surface session", msg.err)
		} else {
			m.surface = msg.session
			return m, tea.Batch(
				m.fetchApprovals(),
				m.fetchSurfaceEvents(),
				schedulePoll(),
			)
		}

	case surfaceLifecycleMsg:
		if msg.err != nil {
			m.errMsg = surfaceError("surface "+msg.action, msg.err)
		} else if msg.session.ID != "" {
			if msg.session.OwnerToken == "" {
				msg.session.OwnerToken = m.surface.OwnerToken
			}
			m.surface = msg.session
		}
		if msg.action == "cancel" {
			m.cancelRequested = false
			if msg.err == nil {
				m.streaming = false
				m.submitting = false
				m.focus = focusComposer
				m.composer.Focus()
				m.appendLog(styleHUD.Render("SYSTEM") + "  " + styleMuted.Render("Cancellation acknowledged."))
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
			if m.overlay == nil && len(m.approvals) > 0 {
				m.overlay = newApprovalOverlay(m.approvals[m.approvalIx])
			}
		}

	case surfaceEventsMsg:
		if msg.err != nil {
			m.errMsg = surfaceError("surface events", msg.err)
		} else {
			for _, event := range msg.replay.Events {
				if event.Seq > m.lastSurfaceSeq {
					m.lastSurfaceSeq = event.Seq
				}
				if m.overlay == nil {
					m.overlay = overlayFromSurfaceEvent(event)
				}
			}
		}

	case pollTickMsg:
		if m.surface.ID == "" {
			return m, nil
		}
		return m, tea.Batch(
			m.heartbeatSurface(),
			m.fetchApprovals(),
			m.fetchSurfaceEvents(),
			schedulePoll(),
		)

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
		event := client.RunEvent(msg)
		if m.probeMissionID != "" {
			if outcome := classifyProbeEvent(event); outcome != "" {
				m.probeOutcome = outcome
			}
		}
		m.appendLog(renderEvent(event))
		return m, waitForEvent(m.eventCh)

	case streamDoneMsg:
		m.streaming = false
		m.focus = focusComposer
		m.composer.Focus()
		m.appendLog(styleMuted.Render("stream ended (" + short(m.streamRun) + ")"))
		if m.probeMissionID != "" {
			m.probing = false
			if msg.err != nil {
				m.probeOutcome = "failed"
			} else if m.probeOutcome == "" {
				m.probeOutcome = "live"
			}
			m.appendLog(probeVerdict(m.probeOutcome))
			missionID := m.probeMissionID
			m.probeMissionID = ""
			return m, archiveProbe(m.c, missionID)
		}

	case settingsLoadedMsg:
		m.settingsLoading = false
		if msg.err != nil {
			m.errMsg = "settings: " + msg.err.Error()
		} else {
			form := newSettingsForm(msg.snapshot, msg.models)
			m.settings = &form
		}

	case settingsSavedMsg:
		if m.settings != nil {
			m.settings.busy = false
		}
		if msg.err != nil {
			message := msg.err.Error()
			if apiErr, ok := msg.err.(*client.APIError); ok && apiErr.Remediation != "" {
				message += " - " + apiErr.Remediation
			}
			if m.settings != nil {
				m.settings.message = message
				m.settings.messageBad = true
			}
			return m, nil
		}
		models := []client.Model(nil)
		if m.settings != nil {
			models = m.settings.models
		}
		form := newSettingsForm(msg.snapshot, models)
		form.message = msg.message
		m.settings = &form
		m.appendLog(styleGood.Render(msg.message))
		if msg.probeAfter {
			m.probing = true
			m.probeOutcome = ""
			m.appendLog(styleKey.Render("starting provider probe" + gl.ellipsis))
			return m, startProbe(m.c, m.surface.ID)
		}
		return m, tea.Batch(m.fetchStatus(), m.fetchModes())

	case probeStartedMsg:
		if msg.err != nil {
			m.probing = false
			m.probeOutcome = "failed"
			m.appendLog(styleBad.Render("provider probe failed: " + msg.err.Error()))
		} else {
			m.probeMissionID = msg.missionID
			m.probeOutcome = ""
			m.appendLog(styleGood.Render("provider probe running " + short(msg.runID) + " " + gl.ellipsis))
			return m.beginStream(msg.runID)
		}

	case probeArchivedMsg:
		if msg.err != nil {
			m.appendLog(styleWarn.Render("probe cleanup failed: " + msg.err.Error()))
		}
		return m, m.fetchMissions()
	}

	return m, nil
}

func surfaceError(prefix string, err error) string {
	message := prefix + ": " + err.Error()
	if apiErr, ok := err.(*client.APIError); ok && apiErr.Remediation != "" {
		message += " - " + apiErr.Remediation
	}
	return message
}

func overlayFromSurfaceEvent(event client.SurfaceEvent) *overlayModel {
	var payload struct {
		Type        string   `json:"type"`
		RequestType string   `json:"request_type"`
		Prompt      string   `json:"prompt"`
		Question    string   `json:"question"`
		Options     []string `json:"options"`
	}
	if json.Unmarshal([]byte(event.PayloadJSON), &payload) != nil {
		return nil
	}
	requestType := payload.RequestType
	if requestType == "" {
		requestType = payload.Type
	}
	prompt := payload.Prompt
	if prompt == "" {
		prompt = payload.Question
	}
	switch requestType {
	case "clarify.request":
		return newClarifyOverlay(prompt, payload.Options)
	case "confirm.request":
		return newConfirmOverlay(prompt)
	default:
		return nil
	}
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
		err := c.StreamRun(context.Background(), runID, func(ev client.RunEvent) {
			ch <- ev
		})
		if err != nil {
			ch <- streamFailureEvent(err)
		}
		close(ch)
	}()
	return m, waitForEvent(ch)
}

func (m model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.overlay != nil {
		return m.handleOverlayKey(msg)
	}
	if m.focus == focusSettings {
		return m.handleSettingsKey(msg)
	}
	// Composer owns most keys while focused; only the explicit verbs escape it.
	if m.focus == focusComposer {
		switch msg.String() {
		case "ctrl+c":
			if (m.streaming || m.submitting) && m.surface.ID != "" && m.surface.OwnerToken != "" {
				m.cancelRequested = true
				m.appendLog(styleWarn.Render("CANCEL REQUESTED"))
				return m, m.cancelSurface()
			}
			return m.quit()
		case "enter", "ctrl+s":
			return m.submitComposer()
		case "alt+enter":
			msg.Alt = false
			var cmd tea.Cmd
			m.composer, cmd = m.composer.Update(msg)
			return m, cmd
		case "ctrl+p":
			m.focus = focusSettings
			m.settingsLoading = true
			m.settings = nil
			m.errMsg = ""
			return m, m.fetchSettings()
		case "ctrl+o":
			m.showSidebar = !m.showSidebar
			m.layout()
			return m, nil
		case "esc":
			return m, nil
		}
		var cmd tea.Cmd
		m.composer, cmd = m.composer.Update(msg)
		return m, cmd
	}

	switch msg.String() {
	case "q", "ctrl+c":
		return m.quit()
	case "r":
		m.errMsg = ""
		if m.surface.ID == "" {
			return m, tea.Batch(m.fetchStatus(), m.fetchModes(), m.fetchMissions(), m.createSurface())
		}
		return m, tea.Batch(m.fetchStatus(), m.fetchModes(), m.fetchMissions(), m.fetchApprovals())
	case "tab":
		m.focus = (m.focus + 1) % 2 // cycle missions <-> permissions
		return m, nil
	case "n":
		m.focus = focusComposer
		m.composer.Focus()
		return m, textarea.Blink
	case "s":
		m.focus = focusSettings
		m.settingsLoading = true
		m.settings = nil
		m.errMsg = ""
		return m, m.fetchSettings()
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

func (m model) handleOverlayKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	next, result := m.overlay.update(msg)
	m.overlay = next
	if result == nil {
		return m, nil
	}
	switch result.kind {
	case overlayApproval:
		if result.denied {
			return m, m.rejectTool(result.approval)
		}
		return m, m.approveTool(result.approval, result.value)
	case overlayClarify:
		m.appendLog(styleGood.Render("clarification captured: " + result.value))
	case overlayConfirm:
		m.appendLog(styleGood.Render("confirmation captured: " + result.value))
	}
	return m, nil
}

func (m model) handleSettingsKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c":
		return m.quit()
	case "esc":
		m.focus = focusComposer
		m.composer.Focus()
		return m, nil
	case "ctrl+s":
		return m.saveSettings(false)
	case "ctrl+t":
		return m.saveSettings(true)
	}
	if m.settings == nil || m.settings.busy {
		return m, nil
	}
	return m, m.settings.update(msg)
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
			m.overlay = newApprovalOverlay(m.approvals[m.approvalIx])
			return m, nil
		}
	case "x":
		if m.approvalIx < len(m.approvals) {
			m.overlay = newApprovalOverlay(m.approvals[m.approvalIx])
			m.overlay.cursor = len(m.overlay.options) - 1
			return m, nil
		}
	}
	return m, nil
}

func (m model) quit() (tea.Model, tea.Cmd) {
	if m.surface.ID == "" || m.surface.OwnerToken == "" {
		return m, tea.Quit
	}
	return m, tea.Sequence(m.closeSurface(), tea.Quit)
}

// submitComposer turns the composer text into a mission + executed run.
func (m model) submitComposer() (tea.Model, tea.Cmd) {
	text := strings.TrimSpace(m.composer.Value())
	if text == "" {
		return m, nil
	}
	if handled, updated, cmd := m.executeSlashCommand(text); handled {
		updated.composer.Reset()
		if updated.focus == focusComposer {
			updated.composer.Focus()
		}
		return updated, cmd
	}
	readiness := readinessFor(m.status, mockAllowed())
	if !readiness.CanRun {
		m.focus = focusSettings
		m.settingsLoading = true
		m.settings = nil
		m.errMsg = "LIVE PROVIDER REQUIRED"
		if readiness.Remediation != "" {
			m.errMsg += " - " + readiness.Remediation
		}
		return m, m.fetchSettings()
	}
	title := firstLine(text)
	m.appendLog(renderUserTurn(text))
	m.composer.Reset()
	m.composer.Focus()
	m.focus = focusComposer
	m.submitting = true
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
	// Reserve rows for compact header, composer, and footer.
	h := m.height - 11
	if h < 4 {
		h = 4
	}
	w := m.width - 4
	if m.showSidebar && m.width >= 110 {
		w -= 36
	}
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
	if m.overlay != nil {
		return m.chatOverlayView()
	}
	if m.focus == focusSettings {
		b.WriteString(m.compactHeader() + "\n\n")
		if m.settingsLoading || m.settings == nil {
			b.WriteString(styleMuted.Render("loading provider settings " + gl.ellipsis))
		} else {
			b.WriteString(m.settings.view(m.width))
		}
		b.WriteString("\n\n" + m.logPanel())
		b.WriteString("\n" + m.footer())
		return b.String()
	}
	return m.chatView()
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
	if m.width > 0 && m.width < 100 {
		line = fmt.Sprintf("%s  [%s]\n%s  %s/%s  auth=%s",
			title,
			mode,
			styleMuted.Render(m.gateway),
			styleVal.Render(orDash(m.status.Provider)),
			styleVal.Render(orDash(m.status.Model)),
			styleKey.Render(orDash(m.status.AuthMode)),
		)
	}
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
	return panelStyle(30).Render(strings.TrimRight(b.String(), "\n"))
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
	return panelStyle(40).Render(strings.TrimRight(b.String(), "\n"))
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
	return panelStyle(40).Render(strings.TrimRight(b.String(), "\n"))
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
		body = panelStyle(max(20, m.width-2)).Render(styleMuted.Render("select a mission and press enter, or n to compose a new one"))
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
	if m.overlay != nil {
		return styleMuted.Render("overlay active · background input paused")
	}
	if m.width > 0 && m.width < 100 && m.focus != focusComposer {
		return styleMuted.Render("j/k move | enter action | tab panes | n compose | r refresh | q quit")
	}
	switch m.focus {
	case focusComposer:
		return styleMuted.Render("ctrl+s run · esc cancel · ctrl+c quit")
	case focusSettings:
		return styleMuted.Render("tab fields · left/right mode · ctrl+s save · ctrl+t save + probe · esc close")
	case focusPermissions:
		return styleMuted.Render("j/k move · a/enter approve · x reject · tab missions · n compose · r refresh · q quit")
	default:
		return styleMuted.Render("j/k move · enter stream · tab permissions · n compose · s settings · p perms · r refresh · q quit")
	}
}

func probeVerdict(outcome string) string {
	switch outcome {
	case "live":
		return styleGood.Render("provider probe: LIVE")
	case "mock":
		return styleWarn.Render("provider probe: MOCK MODE")
	default:
		return styleBad.Render("provider probe: FAILED")
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
