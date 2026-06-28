package client

import (
	"context"
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
