export type TerminalOutcome = "normal" | "interrupt";

export type TerminalLifecycle = {
  render: () => Promise<void>;
  waitForExit: () => Promise<TerminalOutcome>;
  cleanup: () => Promise<void>;
};

export async function runTerminalLifecycle(
  lifecycle: TerminalLifecycle,
): Promise<TerminalOutcome> {
  let cleaned = false;
  const cleanupOnce = async () => {
    if (cleaned) {
      return;
    }
    cleaned = true;
    await lifecycle.cleanup();
  };

  try {
    await lifecycle.render();
    return await lifecycle.waitForExit();
  } finally {
    await cleanupOnce();
  }
}
