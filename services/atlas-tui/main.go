// Command atlas-tui is the ATLAS terminal workbench sidecar (Go/BubbleTea).
//
// It is a thin client of the ATLAS Rust gateway over HTTP + SSE — the same
// contract the cockpit uses. The Rust runtime and Python services stay
// authoritative (D-022); this binary only renders and takes input.
package main

import (
	"flag"
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"atlas-tui/internal/client"
	"atlas-tui/internal/tui"
)

var (
	version = "dev"
	commit  = "unknown"
)

func versionString() string {
	return fmt.Sprintf("atlas-tui %s (%s)", version, commit)
}

func main() {
	gateway := flag.String("gateway", envOr("ATLAS_GATEWAY_URL", "http://127.0.0.1:8484"),
		"ATLAS gateway base URL")
	showVersion := flag.Bool("version", false, "print atlas-tui build identity")
	flag.Parse()
	if *showVersion {
		fmt.Println(versionString())
		return
	}

	c := client.New(*gateway)
	prog := tea.NewProgram(tui.New(c, *gateway), tea.WithAltScreen())
	if _, err := prog.Run(); err != nil {
		fmt.Fprintln(os.Stderr, "atlas-tui:", err)
		os.Exit(1)
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
