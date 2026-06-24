import { describe, expect, test } from "bun:test";

import { runTerminalLifecycle } from "../src/lifecycle";

describe("terminal lifecycle", () => {
  test("cleans up exactly once after normal exit", async () => {
    let cleanupCount = 0;
    const outcome = await runTerminalLifecycle({
      render: async () => undefined,
      waitForExit: async () => "normal",
      cleanup: async () => {
        cleanupCount += 1;
      },
    });

    expect(outcome).toBe("normal");
    expect(cleanupCount).toBe(1);
  });

  test("cleans up exactly once after Ctrl-C", async () => {
    let cleanupCount = 0;
    const outcome = await runTerminalLifecycle({
      render: async () => undefined,
      waitForExit: async () => "interrupt",
      cleanup: async () => {
        cleanupCount += 1;
      },
    });

    expect(outcome).toBe("interrupt");
    expect(cleanupCount).toBe(1);
  });

  test("cleans up exactly once when rendering fails", async () => {
    let cleanupCount = 0;
    const failure = new Error("render failed");

    await expect(
      runTerminalLifecycle({
        render: async () => {
          throw failure;
        },
        waitForExit: async () => "normal",
        cleanup: async () => {
          cleanupCount += 1;
        },
      }),
    ).rejects.toBe(failure);

    expect(cleanupCount).toBe(1);
  });
});
