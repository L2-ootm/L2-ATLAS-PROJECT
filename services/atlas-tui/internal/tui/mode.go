package tui

// mode.go — default agent modes (MiMo-style Build / Plan / Compose) and the
// rotating idle tip line. A mode is a client-side contract shaping the
// submitted mission intent; tools stay gated by the permission broker
// regardless, so Plan/Compose are belt-and-suspenders no-execution asks.

import "github.com/charmbracelet/lipgloss"

type agentMode int

const (
	modeBuild agentMode = iota
	modePlan
	modeCompose
	modeCount
)

func (a agentMode) label() string {
	switch a {
	case modePlan:
		return "PLAN"
	case modeCompose:
		return "COMPOSE"
	default:
		return "BUILD"
	}
}

func (a agentMode) color() lipgloss.Color {
	switch a {
	case modePlan:
		return colBlue
	case modeCompose:
		return colGood
	default:
		return colViolet
	}
}

func (a agentMode) hint() string {
	switch a {
	case modePlan:
		return "plan only, no tools or edits"
	case modeCompose:
		return "co-write and refine text, no tools"
	default:
		return "full agent, tools gated by approvals"
	}
}

// wrapIntent shapes the submitted mission intent for the active mode. Build
// passes through; Plan and Compose prepend explicit no-execution contracts.
func (a agentMode) wrapIntent(text string) string {
	switch a {
	case modePlan:
		return "PLAN MODE — produce a concrete, step-by-step plan for the request below. " +
			"Do not execute tools, modify files, or run commands. End with open questions " +
			"and the recommended first action.\n\n" + text
	case modeCompose:
		return "COMPOSE MODE — collaborate on the text below: refine it into a crisp, " +
			"well-structured draft (brief, doc, or message). Do not execute tools or " +
			"modify files. Return the improved draft plus a short list of what changed.\n\n" + text
	default:
		return text
	}
}

func (a agentMode) next() agentMode { return (a + 1) % modeCount }
func (a agentMode) prev() agentMode { return (a + modeCount - 1) % modeCount }

// modeByName resolves an operator-typed mode name; ok=false when unknown.
func modeByName(name string) (agentMode, bool) {
	switch name {
	case "build":
		return modeBuild, true
	case "plan":
		return modePlan, true
	case "compose":
		return modeCompose, true
	}
	return modeBuild, false
}

// idleTips rotate under the idle hero (~10s each at the 300ms tick).
var idleTips = []string{
	"Press tab to cycle Build, Plan, and Compose modes",
	"Run /deep-research <topic> for a structured research brief",
	"/dream consolidates project memory into durable wiki knowledge",
	"/distill mines recent work for reusable workflows",
	"ctrl+p opens provider settings; ctrl+t saves and fires a live probe",
	"/review asks the agent to review uncommitted workspace changes",
	"alt+enter inserts a newline without submitting",
	"ctrl+o toggles the context sidebar in an active conversation",
}

const tipFrames = 33

func idleTip(frame int) string {
	return idleTips[(frame/tipFrames)%len(idleTips)]
}
