package tui

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"atlas-tui/internal/client"
)

// This state machine adapts the Hermes four-choice approval behavior to the
// ATLAS BubbleTea client. It owns presentation and input only; policy, scopes,
// nonces, and durable rules remain authoritative in the runtime broker.
type overlayKind string

const (
	overlayApproval overlayKind = "approval"
	overlayClarify  overlayKind = "clarify"
	overlayConfirm  overlayKind = "confirm"
)

type overlayOption struct {
	label string
	value string
}

type overlayResult struct {
	kind     overlayKind
	approval client.ToolApproval
	value    string
	denied   bool
}

type overlayModel struct {
	kind     overlayKind
	title    string
	prompt   string
	approval client.ToolApproval
	options  []overlayOption
	cursor   int
	input    textinput.Model
	freeText bool
}

func newApprovalOverlay(approval client.ToolApproval) *overlayModel {
	prompt := approvalLabel(approval)
	if approval.ToolName != "" && !strings.Contains(prompt, approval.ToolName) {
		prompt = approval.ToolName + " :: " + prompt
	}
	return &overlayModel{
		kind:     overlayApproval,
		title:    "Permission required",
		prompt:   prompt,
		approval: approval,
		options: []overlayOption{
			{label: "Allow once", value: "once"},
			{label: "Allow for this session", value: "session"},
			{label: "Always allow this exact action", value: "durable"},
			{label: "Deny", value: "deny"},
		},
	}
}

func newClarifyOverlay(prompt string, options []string) *overlayModel {
	overlay := &overlayModel{
		kind:   overlayClarify,
		title:  "Agent needs clarification",
		prompt: prompt,
	}
	for _, option := range options {
		overlay.options = append(
			overlay.options,
			overlayOption{label: option, value: option},
		)
	}
	if len(overlay.options) == 0 {
		overlay.freeText = true
		overlay.input = textinput.New()
		overlay.input.Placeholder = "Type your response"
		overlay.input.Focus()
	}
	return overlay
}

func newConfirmOverlay(prompt string) *overlayModel {
	return &overlayModel{
		kind:   overlayConfirm,
		title:  "Confirm action",
		prompt: prompt,
		options: []overlayOption{
			{label: "Yes", value: "yes"},
			{label: "No", value: "no"},
		},
		cursor: 1,
	}
}

func (o overlayModel) update(msg tea.KeyMsg) (*overlayModel, *overlayResult) {
	if msg.String() == "esc" {
		return nil, &overlayResult{
			kind: o.kind, approval: o.approval, value: "deny", denied: true,
		}
	}
	if o.freeText {
		if msg.String() == "enter" {
			value := strings.TrimSpace(o.input.Value())
			if value == "" {
				return &o, nil
			}
			return nil, &overlayResult{kind: o.kind, value: value}
		}
		var cmd tea.Cmd
		o.input, cmd = o.input.Update(msg)
		_ = cmd
		return &o, nil
	}
	switch msg.String() {
	case "up", "k":
		if o.cursor > 0 {
			o.cursor--
		}
	case "down", "j":
		if o.cursor < len(o.options)-1 {
			o.cursor++
		}
	case "1", "2", "3", "4":
		index := int(msg.Runes[0] - '1')
		if index < len(o.options) {
			o.cursor = index
			return o.resolve()
		}
	case "enter":
		return o.resolve()
	}
	return &o, nil
}

func (o overlayModel) resolve() (*overlayModel, *overlayResult) {
	if len(o.options) == 0 || o.cursor >= len(o.options) {
		return &o, nil
	}
	value := o.options[o.cursor].value
	return nil, &overlayResult{
		kind:     o.kind,
		approval: o.approval,
		value:    value,
		denied:   value == "deny" || value == "no",
	}
}

func (o overlayModel) view(width int) string {
	var body strings.Builder
	body.WriteString(styleTitle.Render(o.title) + "\n")
	body.WriteString(styleVal.Render(o.prompt) + "\n")
	if o.kind == overlayApproval {
		if preview := approvalPreview(o.approval); preview != "" {
			body.WriteString("\n" + styleMuted.Render(preview) + "\n")
		}
	}
	body.WriteString("\n")
	if o.freeText {
		body.WriteString(o.input.View())
	} else {
		for index, option := range o.options {
			line := fmt.Sprintf("%d. %s", index+1, option.label)
			if index == o.cursor {
				line = styleSelected.Render("> " + line)
			} else {
				line = "  " + line
			}
			body.WriteString(line + "\n")
		}
	}
	body.WriteString(styleMuted.Render("\n↑/↓ or number · enter select · esc deny/cancel"))
	boxWidth := min(max(44, width-12), 84)
	return lipgloss.NewStyle().
		Width(boxWidth).
		Padding(1, 2).
		Border(lipgloss.DoubleBorder()).
		BorderForeground(colViolet).
		Render(strings.TrimRight(body.String(), "\n"))
}

func approvalPreview(approval client.ToolApproval) string {
	raw := approval.ArgsNormalized
	if raw == "" {
		raw = approval.Args
	}
	if raw == "" {
		return ""
	}
	var parsed any
	if json.Unmarshal([]byte(raw), &parsed) == nil {
		if pretty, err := json.MarshalIndent(parsed, "", "  "); err == nil {
			raw = string(pretty)
		}
	}
	lines := strings.Split(raw, "\n")
	if len(lines) > 10 {
		lines = append(lines[:10], "…")
	}
	return strings.Join(lines, "\n")
}
