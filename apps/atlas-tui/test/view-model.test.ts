import { describe, expect, test } from "bun:test";

import { buildShellViewModel, renderShellSnapshot } from "../src/view-model";
import { selectTerminalProfile } from "../src/terminal/profile";

describe("ATLAS shell view model", () => {
  test("is byte-stable and contains only intake-baseline state", () => {
    const profile = selectTerminalProfile({ ascii: false, noColor: true });
    const first = renderShellSnapshot(buildShellViewModel(profile));
    const second = renderShellSnapshot(buildShellViewModel(profile));

    expect(first).toBe(second);
    expect(first).toContain("ATLAS");
    expect(first).toContain("Workspace: not connected");
    expect(first).toContain("Agent: not connected");
    expect(first).toContain("Mode: intake baseline");
    expect(first).toContain("Type a message after ATLAS contracts are connected");
    expect(first).toContain("Ctrl-C to exit");
    expect(first).not.toMatch(/\d{4}-\d{2}-\d{2}/);
    expect(first).not.toContain("http");
  });

  test("ASCII fallback contains only printable ASCII and newlines", () => {
    const profile = selectTerminalProfile({ ascii: true, noColor: true });
    const snapshot = renderShellSnapshot(buildShellViewModel(profile));

    expect(snapshot).toMatch(/^[\x20-\x7E\n]+$/);
    expect(snapshot).toContain("+");
    expect(snapshot).not.toContain("┌");
  });

  test("terminal capability selection is explicit and deterministic", () => {
    expect(selectTerminalProfile({ ascii: true, noColor: false })).toEqual({
      unicode: false,
      color: true,
    });
    expect(selectTerminalProfile({ ascii: false, noColor: true })).toEqual({
      unicode: true,
      color: false,
    });
  });
});
