package client

import "encoding/json"

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

// Mission is one row of GET /v1/missions ({missions:[...]}).
type Mission struct {
	ID     string `json:"id"`
	Title  string `json:"title"`
	Status string `json:"status"`
}

type missionsEnvelope struct {
	Missions []Mission `json:"missions"`
	Count    int       `json:"count"`
}

// RunEvent is one decoded SSE frame from GET /v1/runs/{id}/stream.
// Name is the SSE event ("audit" | "end" | "stream_error"); Data is its payload.
type RunEvent struct {
	Name string
	Data json.RawMessage
}
