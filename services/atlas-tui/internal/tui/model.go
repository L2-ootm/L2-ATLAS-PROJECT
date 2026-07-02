// Package tui is the ATLAS terminal workbench (BubbleTea).
//
// Reimplements opencode/MiMo terminal patterns ATLAS-native (no donor runtime
// imported). It is a thin client of the ATLAS gateway: a chat-first surface
// whose composer submits a mission + drives a real run end-to-end, with the
// provider mesh, approvals, and settings behind overlays and slash commands.
// It holds no business logic — render + input + HTTP only (D-022).
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
const spinnerInterval = 120 * time.Millisecond

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
type spinnerTickMsg struct{}
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

	items             []transcriptItem
	viewport          viewport.Model
	vpReady           bool
	streaming         bool
	streamRun         string
	eventCh           chan client.RunEvent
	cancelRequested   bool
	lastAssistantText string

	composer   textarea.Model
	submitting bool

	menuMatches []slashCommand
	menuIx      int

	spinFrame   int
	turnStarted time.Time

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
	ta.Placeholder = "Describe a mission or ask anything " + gl.ellipsis
	ta.Prompt = " "
	ta.CharLimit = 8000
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

// busy reports whether agent work is in flight (spinner + cancel semantics).
func (m model) busy() bool {
	return m.submitting || m.streaming
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

func scheduleSpinner() tea.Cmd {
	return tea.Tick(spinnerInterval, func(time.Time) tea.Msg { return spinnerTickMsg{} })
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

	case spinnerTickMsg:
		if !m.busy() && !m.probing {
			return m, nil
		}
		m.spinFrame++
		return m, scheduleSpinner()

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
				m.appendSystem("Cancellation acknowledged.")
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
			m.appendItem(transcriptItem{
				kind: itemError, label: "approval",
				text: msg.verb + " failed: " + msg.err.Error(),
			})
		} else {
			m.appendItem(transcriptItem{
				kind: itemNotice,
				text: fmt.Sprintf("%s %s [%s]", msg.verb, msg.approval.ToolName, msg.approval.Status),
			})
		}
		return m, m.fetchApprovals()

	case missionCreatedMsg:
		if msg.err != nil {
			m.submitting = false
			m.appendItem(transcriptItem{kind: itemError, label: "dispatch", text: msg.err.Error()})
		} else {
			return m, tea.Batch(m.fetchMissions(), m.startRun(msg.mission.ID))
		}

	case runStartedMsg:
		if msg.err != nil {
			m.submitting = false
			m.appendItem(transcriptItem{kind: itemError, label: "run start", text: msg.err.Error()})
		} else {
			return m.beginStream(msg.runID)
		}

	case latestRunMsg:
		if msg.err != nil {
			m.appendItem(transcriptItem{kind: itemError, label: "run lookup", text: msg.err.Error()})
		} else if msg.runID == "" {
			m.appendSystem("no runs on this mission yet")
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
		m.applyRunEvent(event)
		return m, waitForEvent(m.eventCh)

	case streamDoneMsg:
		m.streaming = false
		m.submitting = false
		m.focus = focusComposer
		m.composer.Focus()
		if m.probeMissionID != "" {
			m.probing = false
			if msg.err != nil {
				m.probeOutcome = "failed"
			} else if m.probeOutcome == "" {
				m.probeOutcome = "live"
			}
			m.appendItem(probeVerdictItem(m.probeOutcome))
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
		m.appendItem(transcriptItem{kind: itemNotice, text: msg.message})
		if msg.probeAfter {
			m.probing = true
			m.probeOutcome = ""
			m.appendSystem("starting provider probe" + gl.ellipsis)
			return m, tea.Batch(startProbe(m.c, m.surface.ID), scheduleSpinner())
		}
		return m, tea.Batch(m.fetchStatus(), m.fetchModes())

	case probeStartedMsg:
		if msg.err != nil {
			m.probing = false
			m.probeOutcome = "failed"
			m.appendItem(transcriptItem{kind: itemError, label: "probe", text: msg.err.Error()})
		} else {
			m.probeMissionID = msg.missionID
			m.probeOutcome = ""
			return m.beginStream(msg.runID)
		}

	case probeArchivedMsg:
		if msg.err != nil {
			m.appendSystem("probe cleanup failed: " + msg.err.Error())
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

// applyRunEvent folds one SSE event into the transcript: tools complete in
// place via tool_call_id, and terminal-transition summaries that duplicate the
// already-rendered assistant text are dropped.
func (m *model) applyRunEvent(event client.RunEvent) {
	for _, item := range itemsFromEvent(event) {
		switch item.kind {
		case itemAssistant:
			text := strings.TrimSpace(item.text)
			if text == "" || text == m.lastAssistantText {
				continue
			}
			m.lastAssistantText = text
			m.submitting = false
		case itemTool:
			if item.status != "running" && item.callID != "" && m.completeTool(item) {
				continue
			}
		case itemError:
			if item.callID != "" {
				m.completeTool(transcriptItem{
					kind: itemTool, status: "failed", callID: item.callID, label: item.label,
				})
			}
		}
		m.appendItem(item)
	}
}

// completeTool updates the newest matching in-flight tool row; returns true
// when an in-place update happened (no separate line needed).
func (m *model) completeTool(update transcriptItem) bool {
	for i := len(m.items) - 1; i >= 0; i-- {
		it := m.items[i]
		if it.kind == itemTool && it.callID == update.callID && it.status == "running" {
			it.status = update.status
			if update.text != "" {
				it.detail = update.text
			}
			m.items[i] = it
			m.refreshViewport()
			return true
		}
	}
	return false
}

// beginStream wires the SSE consumer for a run id and starts pumping events.
func (m model) beginStream(runID string) (tea.Model, tea.Cmd) {
	m.streaming = true
	m.streamRun = runID
	m.lastAssistantText = ""
	m.eventCh = make(chan client.RunEvent, 64)
	ch := m.eventCh
	c := m.c
	go func() {
		err := c.StreamRun(context.Background(), runID, func(ev client.RunEvent) {
			ch <- ev
		})
		if err != nil {
			ch <- streamFailureEvent(err)
		}
		close(ch)
	}()
	return m, tea.Batch(waitForEvent(ch), scheduleSpinner())
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
		if m.menuOpen() {
			if handled, updated, cmd := m.handleMenuKey(msg); handled {
				return updated, cmd
			}
		}
		switch msg.String() {
		case "ctrl+c":
			if m.busy() && m.surface.ID != "" && m.surface.OwnerToken != "" {
				m.cancelRequested = true
				m.appendSystem("CANCEL REQUESTED")
				return m, m.cancelSurface()
			}
			return m.quit()
		case "enter", "ctrl+s":
			return m.submitComposer()
		case "alt+enter":
			msg.Alt = false
			var cmd tea.Cmd
			m.composer, cmd = m.composer.Update(msg)
			m.syncMenu()
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
		m.syncMenu()
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
		m.appendItem(transcriptItem{kind: itemNotice, text: "clarification captured: " + result.value})
	case overlayConfirm:
		m.appendItem(transcriptItem{kind: itemNotice, text: "confirmation captured: " + result.value})
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
			m.appendSystem("resolving latest run" + gl.ellipsis)
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
		updated.menuMatches = nil
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
	m.appendItem(transcriptItem{kind: itemUser, text: text})
	m.composer.Reset()
	m.menuMatches = nil
	m.composer.Focus()
	m.focus = focusComposer
	m.submitting = true
	m.turnStarted = time.Now()
	return m, tea.Batch(m.submitMission(truncate(title, 120), text), scheduleSpinner())
}

func (m *model) appendItem(item transcriptItem) {
	m.items = append(m.items, item)
	if len(m.items) > 500 {
		m.items = m.items[len(m.items)-500:]
	}
	m.refreshViewport()
}

func (m *model) appendSystem(text string) {
	m.appendItem(transcriptItem{kind: itemSystem, text: text})
}

func (m *model) refreshViewport() {
	if m.vpReady {
		m.viewport.SetContent(renderTranscript(m.items, m.viewport.Width))
		m.viewport.GotoBottom()
	}
}

func probeVerdictItem(outcome string) transcriptItem {
	switch outcome {
	case "live":
		return transcriptItem{kind: itemNotice, text: "provider probe: LIVE"}
	case "mock":
		return transcriptItem{kind: itemSystem, text: "provider probe: MOCK MODE"}
	default:
		return transcriptItem{kind: itemError, label: "probe", text: "provider probe failed"}
	}
}

// layout sizes the scrollback viewport from the current terminal dimensions.
func (m *model) layout() {
	// Reserve rows: header (2), composer surface (5), footer + hints (3),
	// breathing room (1).
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
	m.viewport.SetContent(renderTranscript(m.items, w))
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

func (m model) logPanel() string {
	title := styleKey.Render("run stream")
	if m.streaming {
		title += styleGood.Render(" " + gl.live + " live")
	} else if m.submitting {
		title += styleWarn.Render(" " + gl.ellipsis + " submitting")
	}
	body := m.viewport.View()
	if !m.vpReady {
		body = styleMuted.Render("no activity yet")
	}
	return title + "\n" + body
}

func (m model) footer() string {
	if m.overlay != nil {
		return styleMuted.Render("overlay active " + gl.bullet + " background input paused")
	}
	if m.width > 0 && m.width < 100 && m.focus != focusComposer {
		return styleMuted.Render("j/k move | enter action | tab panes | n compose | r refresh | q quit")
	}
	switch m.focus {
	case focusComposer:
		return m.chatFooter()
	case focusSettings:
		return styleMuted.Render("tab fields · left/right mode · ctrl+s save · ctrl+t save + probe · esc close")
	case focusPermissions:
		return styleMuted.Render("j/k move · a/enter approve · x reject · tab missions · n compose · r refresh · q quit")
	default:
		return styleMuted.Render("j/k move · enter stream · tab permissions · n compose · s settings · p perms · r refresh · q quit")
	}
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
