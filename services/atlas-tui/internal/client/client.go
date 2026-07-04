// Package client is a thin HTTP + SSE client for the ATLAS Rust gateway.
//
// The TUI holds no business logic (D-022): it renders what the gateway returns
// over the same contract the cockpit uses. All state — auth, config, runs,
// permissions — lives behind the gateway in the Python runtime.
package client

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
)

// modelsCacheTTL bounds how long a fetched model catalog is reused before
// Models() re-queries the gateway. Settings opens Config+Models together on
// every visit; without this, repeat visits pay a full catalog fetch each time.
const modelsCacheTTL = 5 * time.Minute

// Client talks to one ATLAS gateway base URL.
type Client struct {
	BaseURL string
	http    *http.Client

	modelsMu      sync.Mutex
	cachedModels  []Model
	modelsFetched time.Time
	modelsGen     uint64 // bumped by invalidateModelsCache; guards against an
	// in-flight fetch started before an invalidation overwriting the cache
	// with stale data after that invalidation lands.
}

// APIError preserves the gateway's structured remediation for UI surfaces.
type APIError struct {
	Method          string
	Path            string
	StatusCode      int
	Code            string
	Message         string
	Remediation     string
	CurrentRevision int64
}

func (e *APIError) Error() string {
	if e.Message != "" {
		return e.Message
	}
	return fmt.Sprintf("%s %s: %s", e.Method, e.Path, http.StatusText(e.StatusCode))
}

// New builds a Client for the given gateway base URL (e.g. http://127.0.0.1:8484).
func New(baseURL string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		http:    &http.Client{Timeout: 15 * time.Second},
	}
}

func (c *Client) getJSON(ctx context.Context, path string, out any) error {
	return c.requestJSON(ctx, http.MethodGet, path, nil, out)
}

// postJSON sends body as JSON to path and decodes a 2xx response into out
// (out may be nil to discard). Non-2xx surfaces the gateway's status line.
func (c *Client) postJSON(ctx context.Context, path string, body, out any) error {
	return c.requestJSON(ctx, http.MethodPost, path, body, out)
}

func (c *Client) requestJSON(
	ctx context.Context,
	method string,
	path string,
	body any,
	out any,
) error {
	return c.requestJSONWithOwner(ctx, method, path, body, out, "")
}

func (c *Client) requestJSONWithOwner(
	ctx context.Context,
	method string,
	path string,
	body any,
	out any,
	ownerToken string,
) error {
	var rdr *bytes.Reader
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			return err
		}
		rdr = bytes.NewReader(raw)
	} else {
		rdr = bytes.NewReader(nil)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, rdr)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if ownerToken != "" {
		req.Header.Set("X-Atlas-Surface-Owner", ownerToken)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var payload struct {
			Error struct {
				Code        string `json:"code"`
				Message     string `json:"message"`
				Remediation string `json:"remediation"`
			} `json:"error"`
			CurrentRevision int64 `json:"current_revision"`
		}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		if resp.StatusCode == http.StatusNotFound &&
			strings.HasPrefix(path, "/v1/surface-sessions") &&
			payload.Error.Code == "" {
			payload.Error.Code = "gateway_upgrade_required"
			payload.Error.Message = "the ATLAS gateway does not support shared surface sessions"
			payload.Error.Remediation = "upgrade and restart the ATLAS gateway before using this TUI"
		}
		return &APIError{
			Method:          method,
			Path:            path,
			StatusCode:      resp.StatusCode,
			Code:            payload.Error.Code,
			Message:         payload.Error.Message,
			Remediation:     payload.Error.Remediation,
			CurrentRevision: payload.CurrentRevision,
		}
	}
	if out == nil {
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

// CreateSurface attaches this TUI to the shared session/permission contracts.
// There is deliberately no legacy fallback: unscoped approval mutation is not
// safe when the gateway lacks the surface-session endpoints.
func (c *Client) CreateSurface(
	ctx context.Context,
	surfaceKind string,
	workspaceKind string,
	projectID string,
) (SurfaceSession, error) {
	var session SurfaceSession
	body := map[string]any{
		"surface_kind":   surfaceKind,
		"workspace_kind": workspaceKind,
	}
	if projectID != "" {
		body["project_id"] = projectID
	}
	err := c.postJSON(ctx, "/v1/surface-sessions", body, &session)
	return session, err
}

func (c *Client) mutateSurface(
	ctx context.Context,
	session SurfaceSession,
	action string,
) (SurfaceSession, error) {
	var updated SurfaceSession
	if session.ID == "" || session.OwnerToken == "" {
		return updated, errors.New("surface mutation requires session id and owner token")
	}
	path := "/v1/surface-sessions/" + url.PathEscape(session.ID) + "/" + action
	err := c.postJSON(ctx, path, map[string]string{"owner_token": session.OwnerToken}, &updated)
	return updated, err
}

// HeartbeatSurface keeps the approval channel and owner lease alive.
func (c *Client) HeartbeatSurface(
	ctx context.Context,
	session SurfaceSession,
) (SurfaceSession, error) {
	return c.mutateSurface(ctx, session, "heartbeat")
}

// CancelSurface requests cooperative cancellation of active work owned by this session.
func (c *Client) CancelSurface(
	ctx context.Context,
	session SurfaceSession,
) (SurfaceSession, error) {
	return c.mutateSurface(ctx, session, "cancel")
}

// CloseSurface cleanly releases this TUI's owner-bound shared session.
func (c *Client) CloseSurface(
	ctx context.Context,
	session SurfaceSession,
) (SurfaceSession, error) {
	return c.mutateSurface(ctx, session, "close")
}

// SurfaceEvents replays normalized events strictly after the supplied cursor.
func (c *Client) SurfaceEvents(
	ctx context.Context,
	session SurfaceSession,
	afterSeq int64,
) (SurfaceEventReplay, error) {
	var replay SurfaceEventReplay
	if session.ID == "" || session.OwnerToken == "" {
		return replay, errors.New("event replay requires session id and owner token")
	}
	query := url.Values{
		"after_seq": []string{strconv.FormatInt(afterSeq, 10)},
	}
	path := "/v1/surface-sessions/" + url.PathEscape(session.ID) +
		"/events?" + query.Encode()
	err := c.requestJSONWithOwner(
		ctx, http.MethodGet, path, nil, &replay, session.OwnerToken,
	)
	return replay, err
}

// Config returns the masked provider config and optimistic revision.
func (c *Client) Config(ctx context.Context) (ConfigSnapshot, error) {
	var snapshot ConfigSnapshot
	err := c.getJSON(ctx, "/v1/config", &snapshot)
	return snapshot, err
}

// PatchConfig atomically applies dotted control-plane changes.
func (c *Client) PatchConfig(
	ctx context.Context,
	expectedRevision int64,
	changes map[string]any,
) (ConfigSnapshot, error) {
	var snapshot ConfigSnapshot
	body := map[string]any{
		"expected_revision": expectedRevision,
		"changes":           changes,
	}
	err := c.requestJSON(ctx, http.MethodPatch, "/v1/config", body, &snapshot)
	if err == nil {
		c.invalidateModelsCache()
	}
	return snapshot, err
}

// Models lists the shared model catalog exposed by the gateway, cached for
// modelsCacheTTL. PatchConfig invalidates the cache (a provider/model change
// can change which entries are active).
func (c *Client) Models(ctx context.Context) ([]Model, error) {
	c.modelsMu.Lock()
	if c.cachedModels != nil && time.Since(c.modelsFetched) < modelsCacheTTL {
		// Copy out: callers that sort/filter the returned slice in place must
		// not corrupt the shared cache backing array for other callers within
		// the TTL window.
		models := append([]Model(nil), c.cachedModels...)
		c.modelsMu.Unlock()
		return models, nil
	}
	gen := c.modelsGen
	c.modelsMu.Unlock()

	var env modelsEnvelope
	if err := c.getJSON(ctx, "/v1/models", &env); err != nil {
		return nil, err
	}

	c.modelsMu.Lock()
	// Only commit if no invalidation happened while this fetch was in flight —
	// otherwise a slow pre-invalidation response would resurrect stale data.
	// Cache stores its own copy so a caller mutating the returned slice in
	// place can't corrupt it for the next cache hit.
	if c.modelsGen == gen {
		c.cachedModels = append([]Model(nil), env.Models...)
		c.modelsFetched = time.Now()
	}
	c.modelsMu.Unlock()
	return env.Models, nil
}

// invalidateModelsCache forces the next Models() call to re-fetch, and fences
// off any fetch already in flight from a stale write after this point.
func (c *Client) invalidateModelsCache() {
	c.modelsMu.Lock()
	c.cachedModels = nil
	c.modelsGen++
	c.modelsMu.Unlock()
}

// StoreAPIKey crosses the loopback HTTP boundary once; the gateway then sends
// the secret to the Python owner over stdin, never argv.
func (c *Client) StoreAPIKey(
	ctx context.Context,
	provider string,
	apiKey string,
	baseURL string,
) (AuthStatus, error) {
	var status AuthStatus
	if !isLoopbackURL(c.BaseURL) {
		return status, errors.New("credential writes require a loopback ATLAS gateway")
	}
	body := struct {
		Provider string `json:"provider"`
		APIKey   string `json:"api_key"`
		BaseURL  string `json:"base_url,omitempty"`
	}{
		Provider: provider,
		APIKey:   apiKey,
		BaseURL:  baseURL,
	}
	err := c.postJSON(ctx, "/v1/auth/providers", body, &status)
	return status, err
}

func isLoopbackURL(raw string) bool {
	parsed, err := url.Parse(raw)
	if err != nil {
		return false
	}
	host := parsed.Hostname()
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

// ImportCodex delegates token ownership and refresh to the Hermes foundation.
func (c *Client) ImportCodex(ctx context.Context) (CodexImportResult, error) {
	var result CodexImportResult
	err := c.postJSON(ctx, "/v1/auth/codex/import", map[string]any{}, &result)
	return result, err
}

// ArchiveMission removes an ephemeral probe from the active mission list.
func (c *Client) ArchiveMission(ctx context.Context, missionID string) error {
	return c.postJSON(
		ctx,
		"/v1/missions/"+missionID+"/archive",
		map[string]int{"delete_after_days": 1},
		nil,
	)
}

// ProviderStatus resolves the active provider (mock-vs-live verdict included).
func (c *Client) ProviderStatus(ctx context.Context) (ProviderStatus, error) {
	var s ProviderStatus
	err := c.getJSON(ctx, "/v1/provider/status", &s)
	return s, err
}

// ProviderModes returns the four-way "which ways can I wire?" board.
func (c *Client) ProviderModes(ctx context.Context) ([]ProviderMode, error) {
	var m []ProviderMode
	err := c.getJSON(ctx, "/v1/provider/modes", &m)
	return m, err
}

// FreellmapiStatus reports the external FreeLLMAPI sidecar's liveness.
func (c *Client) FreellmapiStatus(ctx context.Context) (FreellmapiStatus, error) {
	var s FreellmapiStatus
	err := c.getJSON(ctx, "/v1/freellmapi/status", &s)
	return s, err
}

// FreellmapiStart asks the gateway to bring the FreeLLMAPI sidecar up.
func (c *Client) FreellmapiStart(ctx context.Context) (FreellmapiAction, error) {
	var r FreellmapiAction
	err := c.postJSON(ctx, "/v1/freellmapi/start", map[string]any{}, &r)
	return r, err
}

// FreellmapiStop stops the CLI-managed FreeLLMAPI sidecar process.
func (c *Client) FreellmapiStop(ctx context.Context) (FreellmapiAction, error) {
	var r FreellmapiAction
	err := c.postJSON(ctx, "/v1/freellmapi/stop", map[string]any{}, &r)
	return r, err
}

// Missions lists recent missions.
func (c *Client) Missions(ctx context.Context) ([]Mission, error) {
	var env missionsEnvelope
	if err := c.getJSON(ctx, "/v1/missions", &env); err != nil {
		return nil, err
	}
	return env.Missions, nil
}

// LatestRunID returns the most recent run id for a mission, or "" if none.
// Decodes GET /v1/missions/{id} flexibly so it survives detail-shape changes.
func (c *Client) LatestRunID(ctx context.Context, missionID string) (string, error) {
	var detail struct {
		Runs []struct {
			ID string `json:"id"`
		} `json:"runs"`
	}
	if err := c.getJSON(ctx, "/v1/missions/"+missionID, &detail); err != nil {
		return "", err
	}
	if len(detail.Runs) == 0 {
		return "", nil
	}
	return detail.Runs[len(detail.Runs)-1].ID, nil
}

// CreateMission creates a mission (POST /v1/missions) and returns it. The
// gateway dispatches `atlas mission create` (D-022); title must be non-empty.
func (c *Client) CreateMission(ctx context.Context, title, intent string) (Mission, error) {
	var env createMissionEnvelope
	body := map[string]string{"title": title, "intent": intent}
	if err := c.postJSON(ctx, "/v1/missions", body, &env); err != nil {
		return Mission{}, err
	}
	return env.Mission, nil
}

// StartRun starts a run on a mission (POST /v1/missions/{id}/run) and returns
// the new run id. With execute=true the gateway spawns a detached `run exec`
// so the run drives to completion in the background and streams audit events.
func (c *Client) StartRun(
	ctx context.Context,
	missionID string,
	agent string,
	execute bool,
	surfaceSessionID string,
) (string, error) {
	if agent == "" {
		agent = "native"
	}
	var env startRunEnvelope
	body := map[string]any{
		"agent":              agent,
		"execute":            execute,
		"surface_session_id": surfaceSessionID,
	}
	if err := c.postJSON(ctx, "/v1/missions/"+missionID+"/run", body, &env); err != nil {
		return "", err
	}
	return env.Run.ID, nil
}

// ToolApprovals lists only approvals owned by one shared surface session.
func (c *Client) ToolApprovals(
	ctx context.Context,
	status string,
	session SurfaceSession,
) ([]ToolApproval, error) {
	if session.ID == "" || session.OwnerToken == "" {
		return nil, errors.New("approval queue requires session id and owner token")
	}
	query := url.Values{}
	if status != "" {
		query.Set("status", status)
	}
	path := "/v1/surface-sessions/" + url.PathEscape(session.ID) + "/approvals"
	if encoded := query.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var env approvalsEnvelope
	if err := c.requestJSONWithOwner(
		ctx, http.MethodGet, path, nil, &env, session.OwnerToken,
	); err != nil {
		return nil, err
	}
	return env.Approvals, nil
}

func approvalDecisionBody(
	session SurfaceSession,
	approval ToolApproval,
) (map[string]string, error) {
	if session.ID == "" || session.OwnerToken == "" || approval.ID == "" ||
		approval.SurfaceSessionID != session.ID || approval.Nonce == "" {
		return nil, errors.New("approval decision requires matching owner, id, and nonce")
	}
	return map[string]string{
		"nonce": approval.Nonce,
	}, nil
}

// ApproveTool claims and executes a pending request using its replay nonce.
func (c *Client) ApproveTool(
	ctx context.Context,
	session SurfaceSession,
	approval ToolApproval,
	scope string,
) (ToolApproval, error) {
	var decided ToolApproval
	body, err := approvalDecisionBody(session, approval)
	if err != nil {
		return decided, err
	}
	if scope == "" {
		scope = "once"
	}
	body["scope"] = scope
	err = c.requestJSONWithOwner(
		ctx, http.MethodPost,
		"/v1/surface-sessions/"+url.PathEscape(approval.SurfaceSessionID)+
			"/approvals/"+url.PathEscape(approval.ID)+"/approve",
		body,
		&decided,
		session.OwnerToken,
	)
	return decided, err
}

// RejectTool rejects a nonce-bound pending request; it never executes.
func (c *Client) RejectTool(
	ctx context.Context,
	session SurfaceSession,
	approval ToolApproval,
	reason string,
) (ToolApproval, error) {
	var decided ToolApproval
	body, err := approvalDecisionBody(session, approval)
	if err != nil {
		return decided, err
	}
	if reason != "" {
		body["reason"] = reason
	}
	err = c.requestJSONWithOwner(
		ctx, http.MethodPost,
		"/v1/surface-sessions/"+url.PathEscape(approval.SurfaceSessionID)+
			"/approvals/"+url.PathEscape(approval.ID)+"/reject",
		body,
		&decided,
		session.OwnerToken,
	)
	return decided, err
}

// StreamRun consumes GET /v1/runs/{id}/stream (text/event-stream) and delivers
// each decoded frame to emit until the stream ends, the context is cancelled,
// or an error occurs. It blocks; run it in a goroutine. The terminal "end"
// frame is delivered before return.
func (c *Client) StreamRun(ctx context.Context, runID string, emit func(RunEvent)) error {
	url := fmt.Sprintf("%s/v1/runs/%s/stream", c.BaseURL, runID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "text/event-stream")
	// No client timeout for the stream itself; rely on ctx for cancellation.
	streamClient := &http.Client{}
	resp, err := streamClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("stream %s: %s", runID, resp.Status)
	}

	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	var name string
	var data strings.Builder
	flush := func() {
		if name == "" && data.Len() == 0 {
			return
		}
		emit(RunEvent{Name: name, Data: json.RawMessage(data.String())})
		name = ""
		data.Reset()
	}
	for scanner.Scan() {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}
		line := scanner.Text()
		switch {
		case line == "": // blank line terminates an SSE frame
			flush()
		case strings.HasPrefix(line, "event:"):
			name = strings.TrimSpace(strings.TrimPrefix(line, "event:"))
		case strings.HasPrefix(line, "data:"):
			data.WriteString(strings.TrimSpace(strings.TrimPrefix(line, "data:")))
		}
	}
	flush()
	return scanner.Err()
}
