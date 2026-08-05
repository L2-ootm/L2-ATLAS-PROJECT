package client

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestCrossSurfaceReferenceMissionsUseGatewayClientContract(t *testing.T) {
	path := filepath.Join("..", "..", "..", "agent-runtime", "tests", "fixtures", "reference_missions.json")
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Surfaces []string `json:"surfaces"`
		Missions []struct {
			ID                 string `json:"id"`
			SurfaceProjections map[string][]struct {
				EventIndex int    `json:"event_index"`
				Kind       string `json:"kind"`
			} `json:"surface_projections"`
		} `json:"missions"`
	}
	if err := json.Unmarshal(body, &fixture); err != nil {
		t.Fatal(err)
	}
	if len(fixture.Missions) != 8 {
		t.Fatalf("reference mission count = %d, want 8", len(fixture.Missions))
	}
	for _, mission := range fixture.Missions {
		projection := mission.SurfaceProjections["go_tui"]
		if len(projection) == 0 {
			t.Fatalf("%s has no Go TUI gateway projection", mission.ID)
		}
		for index, event := range projection {
			if event.EventIndex != index {
				t.Fatalf("%s event[%d].event_index = %d, want ordered gateway event", mission.ID, index, event.EventIndex)
			}
		}
	}
}
