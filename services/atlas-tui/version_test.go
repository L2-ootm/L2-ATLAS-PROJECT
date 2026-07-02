package main

import (
	"strings"
	"testing"
)

func TestVersionStringCarriesBuildIdentity(t *testing.T) {
	oldVersion, oldCommit := version, commit
	version, commit = "1.1.0", "abc1234"
	t.Cleanup(func() { version, commit = oldVersion, oldCommit })

	got := versionString()
	if !strings.Contains(got, "atlas-tui 1.1.0") || !strings.Contains(got, "abc1234") {
		t.Fatalf("version string missing build identity: %q", got)
	}
}
