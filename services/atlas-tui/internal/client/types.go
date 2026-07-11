package client

import "encoding/json"

// ProviderConfig is the editable provider slice of GET /v1/config.
type ProviderConfig struct {
	Name            string  `json:"name"`
	Model           string  `json:"model"`
	AuthMode        string  `json:"auth_mode"`
	APIKey          string  `json:"api_key"`
	BaseURL         *string `json:"base_url"`
	ReasoningEffort string  `json:"reasoning_effort"`
}

// ConfigSnapshot carries the optimistic revision required by PATCH /v1/config.
// Other config sections remain owned by the control plane and are intentionally
// omitted from this focused TUI contract.
type ConfigSnapshot struct {
	SchemaVersion int            `json:"schema_version"`
	Revision      int64          `json:"revision"`
	Provider      ProviderConfig `json:"provider"`
}

// Model mirrors one row in the GET /v1/models envelope.
type Model struct {
	ModelID   string `json:"model_id"`
	Provider  string `json:"provider"`
	Source    string `json:"source"`
	FirstSeen string `json:"first_seen"`
	LastSeen  string `json:"last_seen"`
	Active    bool   `json:"active"`
}

type modelsEnvelope struct {
	Models []Model `json:"models"`
	Count  int     `json:"count"`
}

// AuthStatus is a masked auth-store result. It never contains credential bytes.
type AuthStatus struct {
	Provider     string  `json:"provider"`
	AuthType     string  `json:"auth_type"`
	Status       string  `json:"status"`
	Source       string  `json:"source"`
	Health       string  `json:"health"`
	UpdatedAt    *string `json:"updated_at"`
	RedactedHint string  `json:"redacted_hint"`
	Remediation  *string `json:"remediation"`
}

// CodexImportResult is the secret-free outcome from the delegated import.
type CodexImportResult struct {
	Imported bool   `json:"imported"`
	Reason   string `json:"reason"`
}

// ProviderStatus mirrors GET /v1/provider/status (atlas provider status --json).
type ProviderStatus struct {
	Provider           string  `json:"provider"`
	Model              string  `json:"model"`
	AuthMode           string  `json:"auth_mode"`
	AuthModeLabel      string  `json:"auth_mode_label"`
	BaseURL            *string `json:"base_url"`
	CredentialsPresent bool    `json:"credentials_present"`
	MockMode           bool    `json:"mock_mode"`
	Remediation        *string `json:"remediation"`
	ReasoningEffort    *string `json:"reasoning_effort"`
	PrivacyWarning     *string `json:"privacy_warning"`
}

// ProviderMode mirrors one row of GET /v1/provider/modes.
type ProviderMode struct {
	Mode        string  `json:"mode"`
	Label       string  `json:"label"`
	Active      bool    `json:"active"`
	Available   bool    `json:"available"`
	Detail      string  `json:"detail"`
	Remediation *string `json:"remediation"`
}

// Mission is one row of GET /v1/missions ({missions:[...]}). Intent/UpdatedAt
// give every surface the same information density as the cockpit mission list.
type Mission struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Status    string `json:"status"`
	Intent    string `json:"intent"`
	UpdatedAt string `json:"updated_at"`
}

type missionsEnvelope struct {
	Missions []Mission `json:"missions"`
	Count    int       `json:"count"`
}

// SurfaceSession is the owner-bound shared work-surface contract. OwnerToken
// is returned only by create/resume and must accompany lifecycle mutations.
type SurfaceSession struct {
	ID             string `json:"id"`
	Agent          string `json:"agent"`
	PermissionMode string `json:"permission_mode"`
	State          string `json:"state"`
	OwnerToken     string `json:"owner_token"`
	Surface        struct {
		Kind      string `json:"kind"`
		SessionID string `json:"session_id"`
	} `json:"surface"`
	Workspace struct {
		Kind      string  `json:"kind"`
		Root      string  `json:"root"`
		ProjectID *string `json:"project_id"`
	} `json:"workspace"`
	Model struct {
		Provider string `json:"provider"`
		ModelID  string `json:"model_id"`
	} `json:"model"`
}

// SurfaceEvent is the normalized, ordered event DTO shared by every surface.
type SurfaceEvent struct {
	SessionID   string `json:"session_id"`
	Seq         int64  `json:"seq"`
	Kind        string `json:"kind"`
	RunID       string `json:"run_id"`
	OccurredAt  string `json:"occurred_at"`
	PayloadJSON string `json:"payload_json"`
}

type SurfaceEventReplay struct {
	SessionID string         `json:"session_id"`
	AfterSeq  int64          `json:"after_seq"`
	Events    []SurfaceEvent `json:"events"`
}

// ToolApproval mirrors one row of a surface-owned approval queue —
// a gated write/shell tool request awaiting an operator decision (10.5 broker).
type ToolApproval struct {
	ID               string          `json:"id"`
	ToolName         string          `json:"tool_name"`
	RiskLevel        string          `json:"risk_level"`
	Args             string          `json:"args"`
	ArgsNormalized   string          `json:"args_normalized"`
	Summary          string          `json:"summary"`
	Status           string          `json:"status"`
	Reason           string          `json:"reason"`
	RunID            string          `json:"run_id"`
	SurfaceSessionID string          `json:"surface_session_id"`
	SurfaceKind      string          `json:"surface_kind"`
	WorkspaceRoot    string          `json:"workspace_root"`
	ExpiryAt         string          `json:"expiry_at"`
	Nonce            string          `json:"nonce"`
	PolicyReceipt    json.RawMessage `json:"policy_receipt"`
	RequestedAt      string          `json:"requested_at"`
}

type approvalsEnvelope struct {
	Approvals []ToolApproval `json:"approvals"`
}

// createMissionEnvelope decodes POST /v1/missions ({mission:{...}, runs:[...]}).
type createMissionEnvelope struct {
	Mission Mission `json:"mission"`
}

// startRunEnvelope decodes POST /v1/missions/{id}/run ({run:{id,...}, executing}).
type startRunEnvelope struct {
	Run struct {
		ID string `json:"id"`
	} `json:"run"`
	Executing bool `json:"executing"`
}

// RunEvent is one decoded SSE frame from GET /v1/runs/{id}/stream.
// Name is the SSE event ("audit" | "end" | "stream_error"); Data is its payload.
type RunEvent struct {
	Name string
	Data json.RawMessage
}

// FreellmapiStatus decodes GET /v1/freellmapi/status (sidecar liveness).
type FreellmapiStatus struct {
	Running     bool   `json:"running"`
	BaseURL     string `json:"base_url"`
	Dir         string `json:"dir"`
	Installed   bool   `json:"installed"`
	Remediation string `json:"remediation"`
}

// FreellmapiAction decodes POST /v1/freellmapi/{start,stop}.
type FreellmapiAction struct {
	OK      bool   `json:"ok"`
	Message string `json:"message"`
}
