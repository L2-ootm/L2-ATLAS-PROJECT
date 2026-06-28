package tui

import (
	"encoding/json"
	"fmt"
	"strings"

	"atlas-tui/internal/client"
)

type auditFrame struct {
	EventType string         `json:"event_type"`
	ToolName  string         `json:"tool_name"`
	Data      map[string]any `json:"data"`
}

func renderEvent(ev client.RunEvent) string {
	switch ev.Name {
	case "end":
		var d struct {
			Status string `json:"status"`
		}
		_ = json.Unmarshal(ev.Data, &d)
		return styleMuted.Render(gl.dash + " run " + orDash(d.Status) + " " + gl.dash)
	case "stream_error":
		var d struct {
			Error string `json:"error"`
		}
		if json.Unmarshal(ev.Data, &d) == nil && d.Error != "" {
			return styleBad.Render("stream error: " + safeInline(d.Error, 160))
		}
		return styleBad.Render("stream error")
	case "audit":
		var frame auditFrame
		if json.Unmarshal(ev.Data, &frame) != nil {
			return styleMuted.Render(gl.bullet + " audit")
		}
		return renderAuditFrame(frame)
	default:
		return styleMuted.Render(gl.bullet + " " + orDash(ev.Name))
	}
}

func renderAuditFrame(frame auditFrame) string {
	data := frame.Data
	kind, _ := data["surface_kind"].(string)
	switch {
	case kind == "reasoning" || (frame.EventType == "llm_call" && boolField(data, "reasoning")):
		return eventLine(styleVioletStyle, "reasoning", firstString(data, "text", "summary"))
	case frame.EventType == "llm_call" || frame.EventType == "model_call_end":
		return eventLine(styleVal, "assistant", firstString(data, "text", "summary"))
	case frame.EventType == "model_call_start":
		return eventLine(styleMuted, "model", firstString(data, "model", "provider"))
	case kind == "diff":
		return renderDiff(data)
	case kind == "retrieval" || frame.EventType == "wiki_update" ||
		frame.EventType == "memory_change":
		return renderRetrieval(data)
	case frame.EventType == "artifact":
		if firstString(data, "path") != "" {
			return renderDiff(data)
		}
		return renderRetrieval(data)
	case frame.EventType == "tool_call" || frame.EventType == "tool_requested":
		detail := firstString(data, "summary", "command", "cmd", "path")
		if detail == "" {
			detail = nestedDisplay(data["input"])
		}
		return eventLine(styleKey, "tool "+orDash(frame.ToolName), detail)
	case frame.EventType == "tool_completed" || frame.EventType == "discord_action":
		return eventLine(styleGood, "tool done "+orDash(frame.ToolName), firstString(data, "summary", "result"))
	case frame.EventType == "failure" || frame.EventType == "tool_failed" ||
		frame.EventType == "provider_fallback" || strings.HasSuffix(frame.EventType, "_failed"):
		detail := joinNonEmpty(
			firstString(data, "error", "message"),
			firstString(data, "stop_reason", "reason"),
		)
		return eventLine(styleBad, "error "+orDash(frame.ToolName), detail)
	default:
		label := orDash(frame.EventType)
		if frame.ToolName != "" {
			label += " " + frame.ToolName
		}
		// Unknown event payloads are intentionally not rendered. The audit
		// ledger is redacted at write time, but an allowlist here prevents a
		// future producer from accidentally displaying opaque credentials.
		return styleMuted.Render(gl.bullet + " " + label)
	}
}

func renderDiff(data map[string]any) string {
	path := firstString(data, "path", "file")
	delta := ""
	if n, ok := numberField(data, "additions"); ok {
		delta = fmt.Sprintf("+%d", n)
	}
	if n, ok := numberField(data, "deletions"); ok {
		delta = joinNonEmpty(delta, fmt.Sprintf("-%d", n))
	}
	return eventLine(styleWarn, "diff", joinNonEmpty(path, delta))
}

func renderRetrieval(data map[string]any) string {
	detail := joinNonEmpty(
		firstString(data, "title", "path", "query"),
		firstString(data, "source"),
	)
	return eventLine(styleVioletStyle, "retrieval", detail)
}

func eventLine(style interface{ Render(...string) string }, label, detail string) string {
	line := gl.bullet + " " + label
	if detail != "" {
		line += " " + safeInline(detail, 240)
	}
	return style.Render(line)
}

func firstString(data map[string]any, keys ...string) string {
	for _, key := range keys {
		if value, ok := data[key].(string); ok && strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func nestedDisplay(value any) string {
	m, ok := value.(map[string]any)
	if !ok {
		return ""
	}
	// Display-only allowlist. Never stringify the whole input map.
	return firstString(m, "cmd", "command", "path", "query", "url")
}

func boolField(data map[string]any, key string) bool {
	value, _ := data[key].(bool)
	return value
}

func numberField(data map[string]any, key string) (int, bool) {
	switch value := data[key].(type) {
	case float64:
		return int(value), true
	case int:
		return value, true
	default:
		return 0, false
	}
}

func safeInline(value string, limit int) string {
	value = strings.Join(strings.Fields(value), " ")
	return truncate(value, limit)
}

func joinNonEmpty(values ...string) string {
	var kept []string
	for _, value := range values {
		if value = strings.TrimSpace(value); value != "" {
			kept = append(kept, value)
		}
	}
	return strings.Join(kept, " ")
}
