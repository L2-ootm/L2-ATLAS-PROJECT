import { createCliRenderer, type CliRenderer } from "@opentui/core";
import { render } from "@opentui/solid";

import { App } from "./app";
import { runCli } from "./cli";
import { runTerminalLifecycle } from "./lifecycle";
import { selectTerminalProfile } from "./terminal/profile";
import { buildShellViewModel } from "./view-model";

async function runInteractive(options: {
  ascii: boolean;
  noColor: boolean;
}): Promise<void> {
  const model = buildShellViewModel(selectTerminalProfile(options));
  let renderer: CliRenderer | undefined;
  let resolveExit: (() => void) | undefined;
  const exitPromise = new Promise<void>((resolve) => {
    resolveExit = resolve;
  });

  await runTerminalLifecycle({
    render: async () => {
      renderer = await createCliRenderer({
        exitOnCtrlC: false,
        useMouse: false,
      });
      await render(
        () => <App model={model} onExit={() => resolveExit?.()} />,
        renderer,
      );
    },
    waitForExit: async () => {
      await exitPromise;
      return "interrupt";
    },
    cleanup: async () => {
      renderer?.destroy();
    },
  });
}

if (import.meta.main) {
  process.exitCode = await runCli(Bun.argv.slice(2), {
    write: (text) => process.stdout.write(text),
    runInteractive,
  });
}
