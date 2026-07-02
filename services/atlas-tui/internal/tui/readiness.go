package tui

import (
	"os"
	"strings"

	"atlas-tui/internal/client"
)

type readinessKind string

const (
	readinessLive         readinessKind = "live"
	readinessUnconfigured readinessKind = "unconfigured"
	readinessDegraded     readinessKind = "degraded"
	readinessMock         readinessKind = "mock"
)

type executionReadiness struct {
	Kind        readinessKind
	CanRun      bool
	Label       string
	Remediation string
}

func readinessFor(status client.ProviderStatus, allowMock bool) executionReadiness {
	remediation := ""
	if status.Remediation != nil {
		remediation = strings.TrimSpace(*status.Remediation)
	}
	if !status.MockMode {
		// A zero-value projection (gateway hiccup, fetch not yet resolved)
		// must never read as LIVE — fail closed to onboarding.
		if strings.TrimSpace(status.Provider) == "" && strings.TrimSpace(status.Model) == "" {
			return executionReadiness{
				Kind: readinessUnconfigured, Label: "PROVIDER SETUP REQUIRED",
				Remediation: remediation,
			}
		}
		return executionReadiness{Kind: readinessLive, CanRun: true, Label: "LIVE"}
	}
	if allowMock {
		return executionReadiness{
			Kind: readinessMock, CanRun: true, Label: "MOCK / EXPLICIT",
			Remediation: remediation,
		}
	}
	if status.CredentialsPresent {
		return executionReadiness{
			Kind: readinessDegraded, Label: "PROVIDER DEGRADED",
			Remediation: remediation,
		}
	}
	return executionReadiness{
		Kind: readinessUnconfigured, Label: "PROVIDER SETUP REQUIRED",
		Remediation: remediation,
	}
}

func mockAllowed() bool {
	value := strings.TrimSpace(strings.ToLower(os.Getenv("ATLAS_TUI_ALLOW_MOCK")))
	return value == "1" || value == "true" || value == "yes"
}
