package client

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
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
		if r.Header.Get("X-Atlas-Surface-Owner") != "owner-1" {
			t.Errorf("missing owner token header")
		}
		if r.URL.Path != "/v1/surface-sessions/surface-1/approvals" {
			t.Errorf("unexpected scoped queue path: %s", r.URL.Path)
		}
		if got := r.URL.Query().Get("status"); got != "pending" {
			t.Errorf("want status=pending, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"approvals":[{"id":"a1","tool_name":"golden_review_write","risk_level":"high","summary":"write x","status":"pending","surface_session_id":"surface-1","nonce":"nonce-1","policy_receipt":"{\"decision\":\"ask\"}"}]}`))
	}))
	defer srv.Close()
	session := SurfaceSession{ID: "surface-1", OwnerToken: "owner-1"}
	as, err := New(srv.URL).ToolApprovals(context.Background(), "pending", session)
	if err != nil {
		t.Fatal(err)
	}
	if len(as) != 1 || as[0].ID != "a1" || as[0].RiskLevel != "high" ||
		as[0].ToolName != "golden_review_write" || as[0].Nonce != "nonce-1" ||
		as[0].SurfaceSessionID != "surface-1" {
		t.Fatalf("unexpected approvals: %+v", as)
	}
}

func TestSurfaceLifecycleUsesOwnerToken(t *testing.T) {
	var calls []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v1/surface-sessions":
			if r.Method != http.MethodPost {
				t.Fatalf("want POST, got %s", r.Method)
			}
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["surface_kind"] != "tui" || body["workspace_kind"] != "global" {
				t.Fatalf("unexpected create body: %+v", body)
			}
			_, _ = w.Write([]byte(`{"id":"surface-1","surface":{"kind":"tui","session_id":"tui-1"},"workspace":{"kind":"global","root":"C:\\atlas"},"agent":"native","model":{"provider":"openrouter","model_id":"test"},"permission_mode":"ask","state":"active","owner_token":"owner-1"}`))
		case "/v1/surface-sessions/surface-1/heartbeat",
			"/v1/surface-sessions/surface-1/close":
			var body map[string]string
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["owner_token"] != "owner-1" {
				t.Fatalf("missing owner token: %+v", body)
			}
			calls = append(calls, r.URL.Path)
			_, _ = w.Write([]byte(`{"id":"surface-1","state":"active","owner_token":"owner-1"}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := New(srv.URL)
	session, err := c.CreateSurface(context.Background(), "tui", "global", "")
	if err != nil {
		t.Fatal(err)
	}
	if session.ID != "surface-1" || session.OwnerToken != "owner-1" ||
		session.Surface.Kind != "tui" {
		t.Fatalf("unexpected session: %+v", session)
	}
	if _, err = c.HeartbeatSurface(context.Background(), session); err != nil {
		t.Fatal(err)
	}
	if _, err = c.CloseSurface(context.Background(), session); err != nil {
		t.Fatal(err)
	}
	if len(calls) != 2 {
		t.Fatalf("want heartbeat and close calls, got %v", calls)
	}
}

func TestSurface404RequiresGatewayUpgrade(t *testing.T) {
	srv := httptest.NewServer(http.NotFoundHandler())
	defer srv.Close()

	_, err := New(srv.URL).CreateSurface(context.Background(), "tui", "global", "")
	var apiErr *APIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("want APIError, got %T: %v", err, err)
	}
	if apiErr.Code != "gateway_upgrade_required" ||
		!strings.Contains(apiErr.Remediation, "gateway") {
		t.Fatalf("unexpected upgrade error: %+v", apiErr)
	}
}

func TestSurfaceEventsUsesReplayCursor(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Atlas-Surface-Owner") != "owner-1" {
			t.Fatalf("missing owner token header")
		}
		if r.URL.Path != "/v1/surface-sessions/surface-1/events" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		if got := r.URL.Query().Get("after_seq"); got != "7" {
			t.Fatalf("want after_seq=7, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"session_id":"surface-1","after_seq":7,"events":[{"session_id":"surface-1","seq":8,"kind":"error","run_id":"run-1","occurred_at":"2026-06-29T00:00:00+00:00","payload_json":"{}"}]}`))
	}))
	defer srv.Close()

	session := SurfaceSession{ID: "surface-1", OwnerToken: "owner-1"}
	replay, err := New(srv.URL).SurfaceEvents(context.Background(), session, 7)
	if err != nil {
		t.Fatal(err)
	}
	if replay.SessionID != "surface-1" || len(replay.Events) != 1 ||
		replay.Events[0].Seq != 8 || replay.Events[0].Kind != "error" {
		t.Fatalf("unexpected replay: %+v", replay)
	}
}

func TestNormalizedEventFixtureParity(t *testing.T) {
	path := filepath.Join(
		"..", "..", "..", "agent-runtime", "tests", "fixtures",
		"surface_event_parity.json",
	)
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		SessionID       string         `json:"session_id"`
		TerminalOutcome string         `json:"terminal_outcome"`
		Events          []SurfaceEvent `json:"events"`
	}
	if err := json.Unmarshal(raw, &fixture); err != nil {
		t.Fatal(err)
	}
	if len(fixture.Events) != 10 || fixture.Events[9].Kind != "completion" {
		t.Fatalf("unexpected fixture events: %+v", fixture.Events)
	}
	for i, event := range fixture.Events {
		if event.SessionID != fixture.SessionID || event.Seq != int64(i) {
			t.Fatalf("event %d breaks session sequence: %+v", i, event)
		}
	}
	var terminal map[string]string
	if err := json.Unmarshal([]byte(fixture.Events[9].PayloadJSON), &terminal); err != nil {
		t.Fatal(err)
	}
	if terminal["status"] != fixture.TerminalOutcome {
		t.Fatalf("terminal mismatch: fixture=%q payload=%q", fixture.TerminalOutcome, terminal["status"])
	}
}

func TestPermissionReceiptFixtureParity(t *testing.T) {
	path := filepath.Join(
		"..", "..", "..", "agent-runtime", "tests", "fixtures",
		"permission_policy_matrix.json",
	)
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Cases []struct {
			ID       string         `json:"id"`
			Expected map[string]any `json:"expected"`
		} `json:"cases"`
	}
	if err := json.Unmarshal(raw, &fixture); err != nil {
		t.Fatal(err)
	}
	if len(fixture.Cases) != 9 {
		t.Fatalf("want 9 policy cases, got %d", len(fixture.Cases))
	}
	validDecision := map[string]bool{"allow": true, "ask": true, "deny": true}
	validLayer := map[string]bool{
		"hardline": true, "master": true, "profile": true,
		"scoped_allow": true, "default": true,
	}
	for _, testCase := range fixture.Cases {
		decision, _ := testCase.Expected["decision"].(string)
		layer, _ := testCase.Expected["source_layer"].(string)
		if !validDecision[decision] || !validLayer[layer] {
			t.Fatalf("invalid canonical receipt for %s: %+v", testCase.ID, testCase.Expected)
		}
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
		if body["surface_session_id"] != "surface-1" {
			t.Errorf("missing surface session: %s", raw)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"run":{"id":"r7"},"executing":true}`))
	}))
	defer srv.Close()
	id, err := New(srv.URL).StartRun(
		context.Background(), "m9", "native", true, "surface-1",
	)
	if err != nil {
		t.Fatal(err)
	}
	if id != "r7" {
		t.Fatalf("want r7, got %q", id)
	}
}

func TestApproveAndRejectTool(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Atlas-Surface-Owner") != "owner-1" {
			t.Fatalf("missing owner token header")
		}
		w.Header().Set("Content-Type", "application/json")
		var body map[string]string
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if _, leaked := body["surface_session_id"]; leaked || body["nonce"] != "nonce-1" {
			t.Fatalf("missing scoped decision identity: %+v", body)
		}
		switch r.URL.Path {
		case "/v1/surface-sessions/surface-1/approvals/a1/approve":
			if body["scope"] != "session" {
				t.Errorf("want session scope, got %+v", body)
			}
			_, _ = w.Write([]byte(`{"id":"a1","tool_name":"t","status":"executed"}`))
		case "/v1/surface-sessions/surface-1/approvals/a1/reject":
			if body["reason"] == "" {
				t.Errorf("expected reason in reject body, got %+v", body)
			}
			_, _ = w.Write([]byte(`{"id":"a1","tool_name":"t","status":"rejected"}`))
		default:
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
	}))
	defer srv.Close()
	c := New(srv.URL)
	approval := ToolApproval{
		ID: "a1", SurfaceSessionID: "surface-1", Nonce: "nonce-1",
	}
	session := SurfaceSession{ID: "surface-1", OwnerToken: "owner-1"}
	ok, err := c.ApproveTool(context.Background(), session, approval, "session")
	if err != nil || ok.Status != "executed" {
		t.Fatalf("approve: %+v err=%v", ok, err)
	}
	rej, err := c.RejectTool(context.Background(), session, approval, "nope")
	if err != nil || rej.Status != "rejected" {
		t.Fatalf("reject: %+v err=%v", rej, err)
	}
}

func TestConfigAndPatchConfig(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/v1/config":
			_, _ = w.Write([]byte(`{"schema_version":1,"revision":4,"provider":{"name":"openrouter","model":"anthropic/claude-sonnet-4","auth_mode":"api_key","api_key":"","base_url":null}}`))
		case r.Method == http.MethodPatch && r.URL.Path == "/v1/config":
			var body struct {
				ExpectedRevision int64          `json:"expected_revision"`
				Changes          map[string]any `json:"changes"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body.ExpectedRevision != 4 || body.Changes["provider.model"] != "openai/gpt-5" {
				t.Fatalf("unexpected patch body: %+v", body)
			}
			_, _ = w.Write([]byte(`{"schema_version":1,"revision":5,"provider":{"name":"openrouter","model":"openai/gpt-5","auth_mode":"api_key","api_key":"","base_url":null}}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := New(srv.URL)
	snapshot, err := c.Config(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if snapshot.Revision != 4 || snapshot.Provider.AuthMode != "api_key" {
		t.Fatalf("unexpected config: %+v", snapshot)
	}
	patched, err := c.PatchConfig(
		context.Background(),
		snapshot.Revision,
		map[string]any{"provider.model": "openai/gpt-5"},
	)
	if err != nil {
		t.Fatal(err)
	}
	if patched.Revision != 5 || patched.Provider.Model != "openai/gpt-5" {
		t.Fatalf("unexpected patched config: %+v", patched)
	}
}

func TestPatchConfigReturnsStructuredConflict(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusConflict)
		_, _ = w.Write([]byte(`{"error":{"code":"config_revision_conflict","message":"stale","remediation":"reload config"},"current_revision":7}`))
	}))
	defer srv.Close()

	_, err := New(srv.URL).PatchConfig(
		context.Background(),
		4,
		map[string]any{"provider.model": "openai/gpt-5"},
	)
	var apiErr *APIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("want APIError, got %T: %v", err, err)
	}
	if apiErr.StatusCode != http.StatusConflict || apiErr.Code != "config_revision_conflict" ||
		apiErr.CurrentRevision != 7 || apiErr.Remediation != "reload config" {
		t.Fatalf("unexpected API error: %+v", apiErr)
	}
}

func TestModelsUsesGatewayEnvelope(t *testing.T) {
	srv := newTestServer(t, map[string]string{
		"/v1/models": `{"models":[{"model_id":"gpt-test","provider":"openrouter","source":"remote","active":true}],"count":1}`,
	})
	defer srv.Close()
	models, err := New(srv.URL).Models(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(models) != 1 || models[0].ModelID != "gpt-test" || !models[0].Active {
		t.Fatalf("unexpected models: %+v", models)
	}
}

func TestStoreAPIKeyReturnsMaskedStatus(t *testing.T) {
	const secret = "stdin-only-secret-9876"
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v1/auth/providers" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		var body map[string]string
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["provider"] != "openrouter" || body["api_key"] != secret ||
			body["base_url"] != "https://example.test/v1" {
			t.Fatalf("unexpected auth body: %+v", body)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"provider":"openrouter","auth_type":"api_key","status":"configured","source":"owned","health":"ok","redacted_hint":"...9876"}`))
	}))
	defer srv.Close()

	status, err := New(srv.URL).StoreAPIKey(
		context.Background(),
		"openrouter",
		secret,
		"https://example.test/v1",
	)
	if err != nil {
		t.Fatal(err)
	}
	if status.Provider != "openrouter" || status.RedactedHint != "...9876" {
		t.Fatalf("unexpected auth status: %+v", status)
	}
}

func TestStoreAPIKeyRejectsNonLoopbackGateway(t *testing.T) {
	const secret = "must-not-leave-this-machine"
	_, err := New("https://gateway.example.com").StoreAPIKey(
		context.Background(),
		"openrouter",
		secret,
		"",
	)
	if err == nil || !strings.Contains(err.Error(), "loopback") {
		t.Fatalf("want loopback rejection, got %v", err)
	}
	if strings.Contains(err.Error(), secret) {
		t.Fatalf("loopback rejection leaked secret: %v", err)
	}
}

func TestImportCodexAndArchiveMission(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v1/auth/codex/import":
			_, _ = w.Write([]byte(`{"imported":true}`))
		case "/v1/missions/probe-1/archive":
			var body map[string]int
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["delete_after_days"] != 1 {
				t.Fatalf("unexpected archive body: %+v", body)
			}
			_, _ = w.Write([]byte(`{"mission":{"id":"probe-1","status":"succeeded"},"runs":[]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := New(srv.URL)
	result, err := c.ImportCodex(context.Background())
	if err != nil || !result.Imported {
		t.Fatalf("import: %+v err=%v", result, err)
	}
	if err := c.ArchiveMission(context.Background(), "probe-1"); err != nil {
		t.Fatal(err)
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
