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
	"fmt"
	"net/http"
	"strings"
	"time"
)

// Client talks to one ATLAS gateway base URL.
type Client struct {
	BaseURL string
	http    *http.Client
}

// New builds a Client for the given gateway base URL (e.g. http://127.0.0.1:8484).
func New(baseURL string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		http:    &http.Client{Timeout: 15 * time.Second},
	}
}

func (c *Client) getJSON(ctx context.Context, path string, out any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.BaseURL+path, nil)
	if err != nil {
		return err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("GET %s: %s", path, resp.Status)
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

// postJSON sends body as JSON to path and decodes a 2xx response into out
// (out may be nil to discard). Non-2xx surfaces the gateway's status line.
func (c *Client) postJSON(ctx context.Context, path string, body, out any) error {
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
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+path, rdr)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("POST %s: %s", path, resp.Status)
	}
	if out == nil {
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
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
func (c *Client) StartRun(ctx context.Context, missionID, agent string, execute bool) (string, error) {
	if agent == "" {
		agent = "native"
	}
	var env startRunEnvelope
	body := map[string]any{"agent": agent, "execute": execute}
	if err := c.postJSON(ctx, "/v1/missions/"+missionID+"/run", body, &env); err != nil {
		return "", err
	}
	return env.Run.ID, nil
}

// ToolApprovals lists tool approvals (GET /v1/tools/approvals). status filters
// by lifecycle ("pending" by default at the CLI; "all" for every row).
func (c *Client) ToolApprovals(ctx context.Context, status string) ([]ToolApproval, error) {
	path := "/v1/tools/approvals"
	if status != "" {
		path += "?status=" + status
	}
	var env approvalsEnvelope
	if err := c.getJSON(ctx, path, &env); err != nil {
		return nil, err
	}
	return env.Approvals, nil
}

// ApproveTool approves + executes a pending tool call (POST .../approve). A
// processed-but-failed tool returns status="failed" (still a 200, not an error).
func (c *Client) ApproveTool(ctx context.Context, id string) (ToolApproval, error) {
	var a ToolApproval
	err := c.postJSON(ctx, "/v1/tools/approvals/"+id+"/approve", nil, &a)
	return a, err
}

// RejectTool rejects a pending tool call (POST .../reject); it never executes.
func (c *Client) RejectTool(ctx context.Context, id, reason string) (ToolApproval, error) {
	var a ToolApproval
	var body any
	if reason != "" {
		body = map[string]string{"reason": reason}
	}
	err := c.postJSON(ctx, "/v1/tools/approvals/"+id+"/reject", body, &a)
	return a, err
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
