package tui

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"atlas-tui/internal/client"
)

func testConfig() client.ConfigSnapshot {
	baseURL := "https://example.test/v1"
	return client.ConfigSnapshot{
		SchemaVersion: 1,
		Revision:      4,
		Provider: client.ProviderConfig{
			Name:     "openrouter",
			Model:    "anthropic/claude-sonnet-4",
			AuthMode: "api_key",
			BaseURL:  &baseURL,
		},
	}
}

func TestSettingsFormCyclesModesAndMasksAPIKey(t *testing.T) {
	form := newSettingsForm(testConfig(), []client.Model{
		{ModelID: "anthropic/claude-sonnet-4", Provider: "openrouter", Active: true},
	})
	form.inputs[settingsAPIKey].SetValue("never-render-this-secret")

	form.cycleMode(1)
	if form.mode() != "oauth_import" {
		t.Fatalf("want oauth_import, got %q", form.mode())
	}
	form.cycleMode(-1)
	if form.mode() != "api_key" {
		t.Fatalf("want api_key, got %q", form.mode())
	}
	view := form.view(100)
	if strings.Contains(view, "never-render-this-secret") {
		t.Fatalf("settings view leaked API key: %s", view)
	}
	if !strings.Contains(view, "****************") {
		t.Fatalf("settings view did not mask API key: %s", view)
	}
}

func TestSaveSettingsStoresAPIKeyThenPatchesRevision(t *testing.T) {
	const secret = "stdin-only-secret-9876"
	var calls []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v1/auth/providers":
			calls = append(calls, "auth")
			var body map[string]string
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["api_key"] != secret {
				t.Fatalf("secret did not cross auth boundary")
			}
			_, _ = w.Write([]byte(`{"provider":"openrouter","auth_type":"api_key","status":"configured","source":"owned","health":"ok","redacted_hint":"...9876"}`))
		case "/v1/config":
			calls = append(calls, "config")
			var body struct {
				ExpectedRevision int64          `json:"expected_revision"`
				Changes          map[string]any `json:"changes"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body.ExpectedRevision != 4 || body.Changes["provider.auth_mode"] != "api_key" {
				t.Fatalf("unexpected config patch: %+v", body)
			}
			_, _ = w.Write([]byte(`{"schema_version":1,"revision":5,"provider":{"name":"openrouter","model":"anthropic/claude-sonnet-4","auth_mode":"api_key","api_key":"","base_url":"https://example.test/v1"}}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	m := New(client.New(srv.URL), srv.URL)
	form := newSettingsForm(testConfig(), nil)
	form.inputs[settingsAPIKey].SetValue(secret)
	m.settings = &form
	updated, cmd := m.saveSettings(false)
	if cmd == nil {
		t.Fatal("save did not return a command")
	}
	if got := updated.settings.inputs[settingsAPIKey].Value(); got != "" {
		t.Fatalf("secret remained in model memory after dispatch: %q", got)
	}
	msg := cmd()
	saved, ok := msg.(settingsSavedMsg)
	if !ok {
		t.Fatalf("want settingsSavedMsg, got %T", msg)
	}
	if saved.err != nil || saved.snapshot.Revision != 5 {
		t.Fatalf("unexpected save result: %+v", saved)
	}
	if strings.Join(calls, ",") != "auth,config" {
		t.Fatalf("want auth before config, got %v", calls)
	}
}

func TestProbeEventClassification(t *testing.T) {
	tests := []struct {
		name string
		ev   client.RunEvent
		want string
	}{
		{
			name: "mock",
			ev: client.RunEvent{Name: "audit", Data: json.RawMessage(
				`{"event_type":"tool_call","tool_name":"mock","data":{"mock_mode":true}}`,
			)},
			want: "mock",
		},
		{
			name: "live",
			ev: client.RunEvent{Name: "audit", Data: json.RawMessage(
				`{"event_type":"model_call_start","data":{"provider":"openrouter"}}`,
			)},
			want: "live",
		},
		{
			name: "failure",
			ev: client.RunEvent{Name: "stream_error", Data: json.RawMessage(
				`{"error":"provider rejected credentials"}`,
			)},
			want: "failed",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := classifyProbeEvent(tc.ev); got != tc.want {
				t.Fatalf("want %q, got %q", tc.want, got)
			}
		})
	}
}

func TestProbeCommandCreatesExecutesAndArchivesOnStartFailure(t *testing.T) {
	var archived bool
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v1/missions":
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"mission":{"id":"probe-1","title":"Provider probe","status":"pending"},"runs":[]}`))
		case "/v1/missions/probe-1/run":
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":{"code":"provider_unavailable","message":"no provider"}}`))
		case "/v1/missions/probe-1/archive":
			archived = true
			_, _ = w.Write([]byte(`{"mission":{"id":"probe-1","status":"failed"},"runs":[]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	msg := startProbe(client.New(srv.URL))()
	started, ok := msg.(probeStartedMsg)
	if !ok {
		t.Fatalf("want probeStartedMsg, got %T", msg)
	}
	if started.err == nil || !archived {
		t.Fatalf("start failure must be returned and probe archived: %+v archived=%v", started, archived)
	}
}

func TestSettingsCommandsDoNotRequireBusinessLogic(t *testing.T) {
	// Compile-time contract: settings operations receive a thin gateway client,
	// and commands remain executable without a BubbleTea program.
	_ = context.Background()
	_ = (*client.Client).PatchConfig
	_ = (*client.Client).StoreAPIKey
	_ = (*client.Client).ImportCodex
}
