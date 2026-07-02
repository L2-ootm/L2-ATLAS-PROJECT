package tui

import (
	"encoding/json"
	"regexp"
	"strings"
	"testing"

	"atlas-tui/internal/client"
)

var ansiPattern = regexp.MustCompile(`\x1b\[[0-9;?]*[ -/]*[@-~]`)

func plain(s string) string {
	return ansiPattern.ReplaceAllString(s, "")
}

func auditEvent(t *testing.T, payload string) client.RunEvent {
	t.Helper()
	if !json.Valid([]byte(payload)) {
		t.Fatalf("invalid test payload: %s", payload)
	}
	return client.RunEvent{Name: "audit", Data: json.RawMessage(payload)}
}

func renderedEvent(t *testing.T, ev client.RunEvent) string {
	t.Helper()
	return plain(renderTranscript(itemsFromEvent(ev), 120))
}

func TestEventItemKinds(t *testing.T) {
	original := gl
	t.Setenv("ATLAS_TUI_ASCII", "1")
	t.Setenv("ATLAS_TUI_UNICODE", "")
	gl = pickGlyphs()
	t.Cleanup(func() { gl = original })

	cases := []struct {
		name    string
		payload string
		wants   []string
	}{
		{
			name:    "assistant text",
			payload: `{"event_type":"llm_call","data":{"text":"hello from atlas"}}`,
			wants:   []string{"ATLAS", "hello from atlas"},
		},
		{
			name:    "reasoning",
			payload: `{"event_type":"llm_call","data":{"surface_kind":"reasoning","text":"checking constraints"}}`,
			wants:   []string{"reasoning", "checking constraints"},
		},
		{
			name:    "tool call",
			payload: `{"event_type":"tool_call","tool_name":"terminal","data":{"input":{"cmd":"go test ./..."}}}`,
			wants:   []string{"terminal", "go test ./..."},
		},
		{
			name:    "diff artifact",
			payload: `{"event_type":"artifact","tool_name":"Write","data":{"surface_kind":"diff","path":"internal/tui/model.go","additions":3,"deletions":1}}`,
			wants:   []string{"internal/tui/model.go", "+3", "-1"},
		},
		{
			name:    "retrieval",
			payload: `{"event_type":"wiki_update","data":{"surface_kind":"retrieval","title":"Provider mesh","source":"wiki"}}`,
			wants:   []string{"retrieval", "Provider mesh", "wiki"},
		},
		{
			name:    "failure",
			payload: `{"event_type":"failure","data":{"error":"provider timed out","stop_reason":"timeout"}}`,
			wants:   []string{"ERROR", "provider timed out", "timeout"},
		},
		{
			name:    "terminal failed transition",
			payload: `{"event_type":"tool_call","data":{"transition":"failed","summary":"Error code: 400 - model rejected"}}`,
			wants:   []string{"ERROR", "model rejected"},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := renderedEvent(t, auditEvent(t, tc.payload))
			for _, want := range tc.wants {
				if !strings.Contains(got, want) {
					t.Fatalf("rendered = %q, want substring %q", got, want)
				}
			}
		})
	}
}

func TestEventsNeverDumpUnknownAuditData(t *testing.T) {
	secret := "sk-never-render-this"
	got := renderedEvent(t, auditEvent(
		t,
		`{"event_type":"custom_event","tool_name":"opaque","data":{"api_key":"`+secret+`","safe":"ignored"}}`,
	))

	if strings.Contains(got, secret) {
		t.Fatalf("unknown audit data leaked into transcript: %q", got)
	}
	if !strings.Contains(got, "custom_event") || !strings.Contains(got, "opaque") {
		t.Fatalf("fallback lost event identity: %q", got)
	}
}

func TestStreamErrorExtractsMessage(t *testing.T) {
	got := renderedEvent(t, client.RunEvent{
		Name: "stream_error",
		Data: json.RawMessage(`{"error":"db_unavailable"}`),
	})
	if !strings.Contains(got, "ERROR") || !strings.Contains(got, "db_unavailable") {
		t.Fatalf("stream error lost detail: %q", got)
	}
}

// --- transcript engine -------------------------------------------------------

func TestLongAssistantResponseSurvivesRendering(t *testing.T) {
	paragraph := strings.Repeat("substance ", 80) // ~800 chars, > old 240 cap
	text := paragraph + "\n\n- **bold** point one\n- point two\n\n```\ncode line\n```"
	items := itemsFromEvent(auditEvent(t,
		`{"event_type":"llm_call","data":{"text":`+mustJSON(t, text)+`}}`))
	rendered := plain(renderTranscript(items, 80))
	if strings.Count(rendered, "substance") != 80 {
		t.Fatalf("assistant text was truncated: %d occurrences", strings.Count(rendered, "substance"))
	}
	for _, want := range []string{"bold", "point two", "code line"} {
		if !strings.Contains(rendered, want) {
			t.Fatalf("markdown-lite lost %q:\n%s", want, rendered)
		}
	}
	for i, line := range strings.Split(rendered, "\n") {
		if len([]rune(line)) > 80 {
			t.Fatalf("line %d exceeds width: %q", i, line)
		}
	}
}

func TestTranscriptRewrapsOnWidthChange(t *testing.T) {
	items := []transcriptItem{{kind: itemAssistant, text: strings.Repeat("wrap ", 40)}}
	wide := plain(renderTranscript(items, 120))
	narrow := plain(renderTranscript(items, 40))
	if len(strings.Split(narrow, "\n")) <= len(strings.Split(wide, "\n")) {
		t.Fatal("narrow render did not produce more wrapped lines")
	}
}

func TestToolCompletionUpdatesInPlace(t *testing.T) {
	m := chatReadyModel(120, 36)
	m.applyRunEvent(auditEvent(t,
		`{"event_type":"tool_call","tool_name":"terminal","tool_call_id":"call-1","data":{"input":{"cmd":"go build"}}}`))
	m.applyRunEvent(auditEvent(t,
		`{"event_type":"tool_completed","tool_name":"terminal","tool_call_id":"call-1","data":{"summary":"exit 0"}}`))

	toolRows := 0
	for _, item := range m.items {
		if item.kind == itemTool {
			toolRows++
			if item.status != "done" {
				t.Fatalf("tool row not completed in place: %+v", item)
			}
		}
	}
	if toolRows != 1 {
		t.Fatalf("tool completion appended a duplicate row: %d rows", toolRows)
	}
}

func TestDuplicateTerminalSummaryIsDeduped(t *testing.T) {
	m := chatReadyModel(120, 36)
	answer := "final response text"
	m.applyRunEvent(auditEvent(t,
		`{"event_type":"llm_call","data":{"text":"`+answer+`","result":true}}`))
	m.applyRunEvent(auditEvent(t,
		`{"event_type":"tool_call","data":{"transition":"succeeded","summary":"`+answer+`"}}`))

	count := 0
	for _, item := range m.items {
		if item.kind == itemAssistant {
			count++
		}
	}
	if count != 1 {
		t.Fatalf("terminal summary duplicated the assistant response: %d blocks", count)
	}
}

func mustJSON(t *testing.T, s string) string {
	t.Helper()
	raw, err := json.Marshal(s)
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}
