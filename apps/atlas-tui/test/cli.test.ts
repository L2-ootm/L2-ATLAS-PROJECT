import { describe, expect, test } from "bun:test";

import { runCli } from "../src/cli";

describe("ATLAS TUI CLI", () => {
  test("snapshot mode prints deterministic ASCII without creating a renderer", async () => {
    const output: string[] = [];
    let rendererCalls = 0;

    const exitCode = await runCli(["--snapshot", "--ascii", "--no-color"], {
      write: (text) => output.push(text),
      runInteractive: async () => {
        rendererCalls += 1;
      },
    });

    expect(exitCode).toBe(0);
    expect(rendererCalls).toBe(0);
    expect(output.join("")).toContain("ATLAS");
    expect(output.join("")).toMatch(/^[\x20-\x7E\n]+$/);
  });

  test("help is ATLAS-only and does not create a renderer", async () => {
    const output: string[] = [];
    let rendererCalls = 0;

    const exitCode = await runCli(["--help"], {
      write: (text) => output.push(text),
      runInteractive: async () => {
        rendererCalls += 1;
      },
    });

    expect(exitCode).toBe(0);
    expect(rendererCalls).toBe(0);
    expect(output.join("")).toContain("ATLAS terminal intake baseline");
    expect(output.join("")).toContain("--snapshot");
  });
});
