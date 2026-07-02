package tui

import (
	"encoding/json"
	"fmt"
	"strings"

	"atlas-tui/internal/client"
)

type auditFrame struct {
	EventType  string         `json:"event_type"`
	ToolName   string         `json:"tool_name"`
	ToolCallID string         `json:"tool_call_id"`
	Data       map[string]any `json:"data"`
}

// itemsFromEvent maps one SSE run event onto zero or more transcript items.
// Unknown payload maps are never dumped: the audit ledger is redacted at
// write time, but the display allowlist here keeps a future producer from
// accidentally rendering opaque credentials.
func itemsFromEvent(ev client.RunEvent) []transcriptItem {
	switch ev.Name {
	case "end":
		var d struct {
			Status string `json:"status"`
		}
		_ = json.Unmarshal(ev.Data, &d)
		return []transcriptItem{runFinishedRule(d.Status)}
	case "stream_error":
		var d struct {
			Error string `json:"error"`
		}
		if json.Unmarshal(ev.Data, &d) == nil && d.Error != "" {
			return []transcriptItem{{kind: itemError, label: "stream", text: d.Error}}
		}
		return []transcriptItem{{kind: itemError, label: "stream", text: "stream error"}}
	case "audit":
		var frame auditFrame
		if json.Unmarshal(ev.Data, &frame) != nil {
			return nil
		}
		return itemsFromAuditFrame(frame)
	default:
		return []transcriptItem{{kind: itemSystem, text: orDash(ev.Name)}}
	}
}

func itemsFromAuditFrame(frame auditFrame) []transcriptItem {
	data := frame.Data
	kind, _ := data["surface_kind"].(string)

	// Mission lifecycle transitions ride on tool_call events without a tool
	// name. "started" is spinner territory (no line); terminal transitions
	// carry the run summary, which the model dedupes against llm_call text.
	if transition := firstString(data, "transition"); transition != "" {
		switch transition {
		case "failed":
			return []transcriptItem{{
				kind: itemError, label: "run",
				text: firstString(data, "summary", "error"),
			}}
		case "succeeded":
			if summary := firstString(data, "summary"); summary != "" {
				return []transcriptItem{{kind: itemAssistant, text: summary}}
			}
		}
		return nil
	}

	switch {
	case kind == "reasoning" || (frame.EventType == "llm_call" && boolField(data, "reasoning")):
		if text := firstString(data, "text", "summary"); text != "" {
			return []transcriptItem{{kind: itemReasoning, text: text}}
		}
		return nil
	case frame.EventType == "llm_call" || frame.EventType == "model_call_end":
		if text := firstString(data, "text", "summary"); text != "" {
			return []transcriptItem{{kind: itemAssistant, text: text}}
		}
		return nil
	case frame.EventType == "model_call_start":
		return []transcriptItem{{
			kind: itemSystem, text: "model " + firstString(data, "model", "provider"),
		}}
	case kind == "diff":
		return []transcriptItem{diffItem(data)}
	case kind == "retrieval" || frame.EventType == "wiki_update" ||
		frame.EventType == "memory_change":
		return []transcriptItem{retrievalItem(data)}
	case frame.EventType == "artifact":
		if firstString(data, "path") != "" {
			return []transcriptItem{diffItem(data)}
		}
		return []transcriptItem{retrievalItem(data)}
	case frame.EventType == "tool_call" || frame.EventType == "tool_requested":
		return toolCallItems(frame)
	case frame.EventType == "tool_completed" || frame.EventType == "discord_action":
		return []transcriptItem{{
			kind: itemTool, status: "done",
			label:  orDash(frame.ToolName),
			callID: frame.ToolCallID,
			text:   firstString(data, "summary", "result"),
		}}
	case frame.EventType == "failure" || frame.EventType == "tool_failed" ||
		frame.EventType == "provider_fallback" || strings.HasSuffix(frame.EventType, "_failed"):
		detail := joinNonEmpty(
			firstString(data, "error", "message"),
			firstString(data, "stop_reason", "reason"),
		)
		return []transcriptItem{{
			kind: itemError, label: frame.ToolName, text: detail, callID: frame.ToolCallID,
		}}
	case frame.EventType == "run_cancelled":
		return []transcriptItem{{kind: itemSystem, text: "run cancelled"}}
	default:
		label := orDash(frame.EventType)
		if frame.ToolName != "" {
			label += " " + frame.ToolName
		}
		return []transcriptItem{{kind: itemSystem, text: label}}
	}
}

// toolCallItems maps a tool_call frame. Runtime markers stay quiet or become
// honest one-line notices; real tools become in-flight rows the model can
// complete in place via tool_call_id.
func toolCallItems(frame auditFrame) []transcriptItem {
	data := frame.Data
	switch frame.ToolName {
	case "native_runtime":
		return nil // engagement marker; the spinner already communicates it
	case "mock":
		return []transcriptItem{{kind: itemSystem, text: "MOCK MODE run (deterministic, no provider)"}}
	case "freellmapi":
		if warning := firstString(data, "privacy_warning"); warning != "" {
			return []transcriptItem{{kind: itemSystem, text: warning}}
		}
	}
	detail := firstString(data, "summary", "command", "cmd", "path")
	if detail == "" {
		detail = nestedDisplay(data["input"])
	}
	return []transcriptItem{{
		kind: itemTool, status: "running",
		label:  orDash(frame.ToolName),
		callID: frame.ToolCallID,
		text:   detail,
	}}
}

func diffItem(data map[string]any) transcriptItem {
	path := firstString(data, "path", "file")
	delta := ""
	if n, ok := numberField(data, "additions"); ok {
		delta = fmt.Sprintf("+%d", n)
	}
	if n, ok := numberField(data, "deletions"); ok {
		delta = joinNonEmpty(delta, fmt.Sprintf("-%d", n))
	}
	return transcriptItem{kind: itemDiff, text: joinNonEmpty(path, delta)}
}

func retrievalItem(data map[string]any) transcriptItem {
	return transcriptItem{
		kind: itemRetrieval,
		text: joinNonEmpty(
			firstString(data, "title", "path", "query"),
			firstString(data, "source"),
		),
	}
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
