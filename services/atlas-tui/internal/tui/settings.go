package tui

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"

	"atlas-tui/internal/client"
)

var providerModes = []string{"api_key", "oauth_import", "claude_code", "freellmapi"}

const (
	settingsProvider = iota
	settingsModel
	settingsBaseURL
	settingsAPIKey
	settingsInputCount
)

const settingsModeField = 0

type settingsForm struct {
	revision   int64
	modeIx     int
	field      int
	inputs     [settingsInputCount]textinput.Model
	models     []client.Model
	busy       bool
	message    string
	messageBad bool
}

type settingsLoadedMsg struct {
	snapshot client.ConfigSnapshot
	models   []client.Model
	err      error
}

type settingsSavedMsg struct {
	snapshot   client.ConfigSnapshot
	probeAfter bool
	message    string
	err        error
}

type probeStartedMsg struct {
	missionID string
	runID     string
	err       error
}

type probeArchivedMsg struct {
	missionID string
	err       error
}

func newSettingsForm(snapshot client.ConfigSnapshot, models []client.Model) settingsForm {
	var form settingsForm
	form.revision = snapshot.Revision
	form.models = models
	for i := range form.inputs {
		form.inputs[i] = textinput.New()
		form.inputs[i].Prompt = ""
		form.inputs[i].CharLimit = 2048
		form.inputs[i].Width = 62
	}
	form.inputs[settingsProvider].Placeholder = "openrouter"
	form.inputs[settingsProvider].SetValue(snapshot.Provider.Name)
	form.inputs[settingsModel].Placeholder = "provider/model"
	form.inputs[settingsModel].SetValue(snapshot.Provider.Model)
	form.inputs[settingsBaseURL].Placeholder = "optional OpenAI-compatible endpoint"
	if snapshot.Provider.BaseURL != nil {
		form.inputs[settingsBaseURL].SetValue(*snapshot.Provider.BaseURL)
	}
	form.inputs[settingsAPIKey].Placeholder = "leave blank to keep existing credential"
	form.inputs[settingsAPIKey].EchoMode = textinput.EchoPassword
	form.inputs[settingsAPIKey].EchoCharacter = '*'
	for i, mode := range providerModes {
		if mode == snapshot.Provider.AuthMode {
			form.modeIx = i
			break
		}
	}
	return form
}

func (f *settingsForm) mode() string {
	return providerModes[f.modeIx]
}

func (f *settingsForm) cycleMode(delta int) {
	f.modeIx = (f.modeIx + delta + len(providerModes)) % len(providerModes)
}

func (f *settingsForm) moveField(delta int) tea.Cmd {
	if f.field > settingsModeField {
		f.inputs[f.field-1].Blur()
	}
	fieldCount := settingsInputCount + 1
	f.field = (f.field + delta + fieldCount) % fieldCount
	if f.field > settingsModeField {
		return f.inputs[f.field-1].Focus()
	}
	return nil
}

func (f *settingsForm) update(msg tea.KeyMsg) tea.Cmd {
	switch msg.String() {
	case "tab", "down":
		return f.moveField(1)
	case "shift+tab", "up":
		return f.moveField(-1)
	case "left":
		if f.field == settingsModeField {
			f.cycleMode(-1)
			return nil
		}
	case "right":
		if f.field == settingsModeField {
			f.cycleMode(1)
			return nil
		}
	}
	if f.field == settingsModeField {
		return nil
	}
	var cmd tea.Cmd
	f.inputs[f.field-1], cmd = f.inputs[f.field-1].Update(msg)
	return cmd
}

func (f settingsForm) view(width int) string {
	panelWidth := min(96, max(34, width-4))
	inputWidth := max(18, panelWidth-22)
	for i := range f.inputs {
		f.inputs[i].Width = inputWidth
	}
	row := func(field int, label, value string) string {
		marker := "  "
		if f.field == field {
			marker = gl.paneBar + " "
		}
		return fmt.Sprintf("%s%-10s %s", marker, label, value)
	}

	var b strings.Builder
	b.WriteString(styleTitle.Render("provider settings"))
	b.WriteString(styleMuted.Render(fmt.Sprintf("  revision %d", f.revision)))
	if f.busy {
		b.WriteString(styleWarn.Render("  saving" + gl.ellipsis))
	}
	b.WriteString("\n")
	b.WriteString(row(settingsModeField, "mode", styleViolet(f.mode())) + "\n")
	b.WriteString(row(settingsProvider+1, "provider", f.inputs[settingsProvider].View()) + "\n")
	b.WriteString(row(settingsModel+1, "model", f.inputs[settingsModel].View()) + "\n")
	b.WriteString(row(settingsBaseURL+1, "base URL", f.inputs[settingsBaseURL].View()) + "\n")
	b.WriteString(row(settingsAPIKey+1, "API key", f.inputs[settingsAPIKey].View()) + "\n")
	if len(f.models) > 0 {
		b.WriteString(styleMuted.Render(fmt.Sprintf(
			"catalog: %d models; current matches are validated by the runtime on save",
			len(f.models),
		)) + "\n")
	}
	switch f.mode() {
	case "oauth_import":
		b.WriteString(styleMuted.Render("Codex login is imported into the Hermes-owned refresh store."))
	case "claude_code":
		b.WriteString(styleMuted.Render("Uses the local Claude Code subscription session; no API key."))
	case "freellmapi":
		b.WriteString(styleWarn.Render("Privacy warning: free endpoints may log prompts; never send secrets."))
	default:
		b.WriteString(styleMuted.Render("A blank API key keeps the existing ATLAS auth-store credential."))
	}
	if f.message != "" {
		messageStyle := styleGood
		if f.messageBad {
			messageStyle = styleBad
		}
		b.WriteString("\n" + messageStyle.Render(f.message))
	}
	return panelStyle(panelWidth).Render(b.String())
}

func (m model) fetchSettings() tea.Cmd {
	return func() tea.Msg {
		snapshot, err := m.c.Config(context.Background())
		if err != nil {
			return settingsLoadedMsg{err: err}
		}
		models, err := m.c.Models(context.Background())
		return settingsLoadedMsg{snapshot: snapshot, models: models, err: err}
	}
}

func (m model) saveSettings(probeAfter bool) (model, tea.Cmd) {
	if m.settings == nil || m.settings.busy {
		return m, nil
	}
	mode := m.settings.mode()
	provider := strings.TrimSpace(m.settings.inputs[settingsProvider].Value())
	modelName := strings.TrimSpace(m.settings.inputs[settingsModel].Value())
	baseURL := strings.TrimSpace(m.settings.inputs[settingsBaseURL].Value())
	apiKey := m.settings.inputs[settingsAPIKey].Value()
	if provider == "" || modelName == "" {
		m.settings.message = "provider and model are required"
		m.settings.messageBad = true
		return m, nil
	}
	if mode == "freellmapi" && baseURL == "" {
		m.settings.message = "FreeLLMAPI mode requires a base URL"
		m.settings.messageBad = true
		return m, nil
	}
	revision := m.settings.revision
	m.settings.inputs[settingsAPIKey].SetValue("")
	m.settings.busy = true
	m.settings.message = ""
	m.settings.messageBad = false
	c := m.c
	return m, func() tea.Msg {
		switch mode {
		case "api_key":
			if apiKey != "" {
				if _, err := c.StoreAPIKey(context.Background(), provider, apiKey, baseURL); err != nil {
					return settingsSavedMsg{probeAfter: probeAfter, err: err}
				}
			}
		case "oauth_import":
			result, err := c.ImportCodex(context.Background())
			if err != nil {
				return settingsSavedMsg{probeAfter: probeAfter, err: err}
			}
			if !result.Imported {
				reason := result.Reason
				if reason == "" {
					reason = "Codex login was not importable"
				}
				return settingsSavedMsg{probeAfter: probeAfter, err: errors.New(reason)}
			}
		}
		var baseURLValue any
		if baseURL != "" {
			baseURLValue = baseURL
		}
		snapshot, err := c.PatchConfig(context.Background(), revision, map[string]any{
			"provider.name":      provider,
			"provider.model":     modelName,
			"provider.auth_mode": mode,
			"provider.base_url":  baseURLValue,
		})
		return settingsSavedMsg{
			snapshot:   snapshot,
			probeAfter: probeAfter,
			message:    "provider configuration saved",
			err:        err,
		}
	}
}

func startProbe(c *client.Client, surfaceSessionID string) tea.Cmd {
	return func() tea.Msg {
		mission, err := c.CreateMission(
			context.Background(),
			"Provider probe",
			"Connectivity probe: reply with exactly ATLAS_PROVIDER_OK. Do not call tools.",
		)
		if err != nil {
			return probeStartedMsg{err: err}
		}
		runID, err := c.StartRun(
			context.Background(),
			mission.ID,
			"native",
			true,
			surfaceSessionID,
		)
		if err != nil {
			archiveErr := c.ArchiveMission(context.Background(), mission.ID)
			if archiveErr != nil {
				err = fmt.Errorf("%w; probe cleanup failed: %v", err, archiveErr)
			}
			return probeStartedMsg{missionID: mission.ID, err: err}
		}
		return probeStartedMsg{missionID: mission.ID, runID: runID}
	}
}

func archiveProbe(c *client.Client, missionID string) tea.Cmd {
	return func() tea.Msg {
		err := c.ArchiveMission(context.Background(), missionID)
		return probeArchivedMsg{missionID: missionID, err: err}
	}
}

func classifyProbeEvent(ev client.RunEvent) string {
	if ev.Name == "stream_error" {
		return "failed"
	}
	if ev.Name == "end" {
		var data struct {
			Status string `json:"status"`
		}
		if json.Unmarshal(ev.Data, &data) == nil && data.Status != "succeeded" {
			return "failed"
		}
		return ""
	}
	if ev.Name != "audit" {
		return ""
	}
	var frame auditFrame
	if json.Unmarshal(ev.Data, &frame) != nil {
		return ""
	}
	if frame.ToolName == "mock" || boolField(frame.Data, "mock_mode") {
		return "mock"
	}
	if frame.EventType == "failure" || frame.EventType == "tool_failed" ||
		strings.HasSuffix(frame.EventType, "_failed") {
		return "failed"
	}
	if frame.EventType == "llm_call" || frame.EventType == "model_call_start" ||
		frame.EventType == "model_call_end" {
		return "live"
	}
	return ""
}

func streamFailureEvent(err error) client.RunEvent {
	data, _ := json.Marshal(map[string]string{"error": err.Error()})
	return client.RunEvent{Name: "stream_error", Data: data}
}
