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

func TestRenderEventKinds(t *testing.T) {
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
			wants:   []string{"assistant", "hello from atlas"},
		},
		{
			name:    "reasoning",
			payload: `{"event_type":"llm_call","data":{"surface_kind":"reasoning","text":"checking constraints"}}`,
			wants:   []string{"reasoning", "checking constraints"},
		},
		{
			name:    "tool call",
			payload: `{"event_type":"tool_call","tool_name":"terminal","data":{"input":{"cmd":"go test ./..."}}}`,
			wants:   []string{"tool", "terminal", "go test ./..."},
		},
		{
			name:    "diff artifact",
			payload: `{"event_type":"artifact","tool_name":"Write","data":{"surface_kind":"diff","path":"internal/tui/model.go","additions":3,"deletions":1}}`,
			wants:   []string{"diff", "internal/tui/model.go", "+3", "-1"},
		},
		{
			name:    "retrieval",
			payload: `{"event_type":"wiki_update","data":{"surface_kind":"retrieval","title":"Provider mesh","source":"wiki"}}`,
			wants:   []string{"retrieval", "Provider mesh", "wiki"},
		},
		{
			name:    "failure",
			payload: `{"event_type":"failure","data":{"error":"provider timed out","stop_reason":"timeout"}}`,
			wants:   []string{"error", "provider timed out", "timeout"},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := plain(renderEvent(auditEvent(t, tc.payload)))
			for _, want := range tc.wants {
				if !strings.Contains(got, want) {
					t.Fatalf("renderEvent() = %q, want substring %q", got, want)
				}
			}
		})
	}
}

func TestRenderEventNeverDumpsUnknownAuditData(t *testing.T) {
	secret := "sk-never-render-this"
	got := plain(renderEvent(auditEvent(
		t,
		`{"event_type":"custom_event","tool_name":"opaque","data":{"api_key":"`+secret+`","safe":"ignored"}}`,
	)))

	if strings.Contains(got, secret) {
		t.Fatalf("unknown audit data leaked into transcript: %q", got)
	}
	if !strings.Contains(got, "custom_event") || !strings.Contains(got, "opaque") {
		t.Fatalf("fallback lost event identity: %q", got)
	}
}

func TestRenderStreamErrorExtractsMessage(t *testing.T) {
	got := plain(renderEvent(client.RunEvent{
		Name: "stream_error",
		Data: json.RawMessage(`{"error":"db_unavailable"}`),
	}))
	if got != "stream error: db_unavailable" {
		t.Fatalf("renderEvent() = %q", got)
	}
}
