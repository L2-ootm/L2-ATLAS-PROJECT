package client

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func newTestServer(t *testing.T, routes map[string]string) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	for path, body := range routes {
		b := body
		mux.HandleFunc(path, func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(b))
		})
	}
	return httptest.NewServer(mux)
}

func TestProviderStatus(t *testing.T) {
	srv := newTestServer(t, map[string]string{
		"/v1/provider/status": `{"provider":"openrouter","model":"x","auth_mode":"api_key","mock_mode":true}`,
	})
	defer srv.Close()
	s, err := New(srv.URL).ProviderStatus(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if s.Provider != "openrouter" || !s.MockMode || s.AuthMode != "api_key" {
		t.Fatalf("unexpected status: %+v", s)
	}
}

func TestProviderModes(t *testing.T) {
	srv := newTestServer(t, map[string]string{
		"/v1/provider/modes": `[{"mode":"api_key","available":false,"active":true},{"mode":"claude_code","available":true,"active":false}]`,
	})
	defer srv.Close()
	modes, err := New(srv.URL).ProviderModes(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(modes) != 2 || modes[0].Mode != "api_key" || !modes[0].Active || !modes[1].Available {
		t.Fatalf("unexpected modes: %+v", modes)
	}
}

func TestMissionsEnvelope(t *testing.T) {
	srv := newTestServer(t, map[string]string{
		"/v1/missions": `{"missions":[{"id":"m1","title":"t","status":"pending"}],"count":1}`,
	})
	defer srv.Close()
	ms, err := New(srv.URL).Missions(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(ms) != 1 || ms[0].ID != "m1" {
		t.Fatalf("unexpected missions: %+v", ms)
	}
}

func TestLatestRunID(t *testing.T) {
	srv := newTestServer(t, map[string]string{
		"/v1/missions/m1": `{"id":"m1","runs":[{"id":"r1"},{"id":"r2"}]}`,
	})
	defer srv.Close()
	id, err := New(srv.URL).LatestRunID(context.Background(), "m1")
	if err != nil {
		t.Fatal(err)
	}
	if id != "r2" {
		t.Fatalf("want r2, got %q", id)
	}
}

func TestToolApprovals(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.URL.Query().Get("status"); got != "pending" {
			t.Errorf("want status=pending, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"approvals":[{"id":"a1","tool_name":"golden_review_write","risk_level":"high","summary":"write x","status":"pending"}]}`))
	}))
	defer srv.Close()
	as, err := New(srv.URL).ToolApprovals(context.Background(), "pending")
	if err != nil {
		t.Fatal(err)
	}
	if len(as) != 1 || as[0].ID != "a1" || as[0].RiskLevel != "high" || as[0].ToolName != "golden_review_write" {
		t.Fatalf("unexpected approvals: %+v", as)
	}
}

func TestCreateMissionSendsBody(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("want POST, got %s", r.Method)
		}
		raw, _ := io.ReadAll(r.Body)
		var body map[string]string
		_ = json.Unmarshal(raw, &body)
		if body["title"] != "Ship it" || body["intent"] != "do the thing" {
			t.Errorf("unexpected body: %s", raw)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"mission":{"id":"m9","title":"Ship it","status":"pending"},"runs":[]}`))
	}))
	defer srv.Close()
	ms, err := New(srv.URL).CreateMission(context.Background(), "Ship it", "do the thing")
	if err != nil {
		t.Fatal(err)
	}
	if ms.ID != "m9" || ms.Title != "Ship it" {
		t.Fatalf("unexpected mission: %+v", ms)
	}
}

func TestStartRunReturnsRunID(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/missions/m9/run" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		raw, _ := io.ReadAll(r.Body)
		var body map[string]any
		_ = json.Unmarshal(raw, &body)
		if body["agent"] != "native" || body["execute"] != true {
			t.Errorf("unexpected body: %s", raw)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"run":{"id":"r7"},"executing":true}`))
	}))
	defer srv.Close()
	id, err := New(srv.URL).StartRun(context.Background(), "m9", "native", true)
	if err != nil {
		t.Fatal(err)
	}
	if id != "r7" {
		t.Fatalf("want r7, got %q", id)
	}
}

func TestApproveAndRejectTool(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v1/tools/approvals/a1/approve":
			_, _ = w.Write([]byte(`{"id":"a1","tool_name":"t","status":"executed"}`))
		case "/v1/tools/approvals/a1/reject":
			raw, _ := io.ReadAll(r.Body)
			var body map[string]string
			_ = json.Unmarshal(raw, &body)
			if body["reason"] == "" {
				t.Errorf("expected reason in reject body, got %s", raw)
			}
			_, _ = w.Write([]byte(`{"id":"a1","tool_name":"t","status":"rejected"}`))
		default:
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
	}))
	defer srv.Close()
	c := New(srv.URL)
	ok, err := c.ApproveTool(context.Background(), "a1")
	if err != nil || ok.Status != "executed" {
		t.Fatalf("approve: %+v err=%v", ok, err)
	}
	rej, err := c.RejectTool(context.Background(), "a1", "nope")
	if err != nil || rej.Status != "rejected" {
		t.Fatalf("reject: %+v err=%v", rej, err)
	}
}

func TestStreamRunParsesSSE(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write([]byte(
			"event: audit\ndata: {\"event_type\":\"tool_call\",\"tool_name\":\"native_runtime\"}\n\n" +
				"event: end\ndata: {\"status\":\"succeeded\"}\n\n"))
	}))
	defer srv.Close()

	var got []RunEvent
	err := New(srv.URL).StreamRun(context.Background(), "r1", func(ev RunEvent) {
		got = append(got, ev)
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("want 2 events, got %d: %+v", len(got), got)
	}
	if got[0].Name != "audit" || got[1].Name != "end" {
		t.Fatalf("unexpected event names: %q, %q", got[0].Name, got[1].Name)
	}
	if string(got[0].Data) != `{"event_type":"tool_call","tool_name":"native_runtime"}` {
		t.Fatalf("unexpected audit data: %s", got[0].Data)
	}
}
