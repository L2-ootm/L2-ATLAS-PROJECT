import { selectTerminalProfile } from "./terminal/profile";
import { buildShellViewModel, renderShellSnapshot } from "./view-model";

const HELP = `ATLAS terminal intake baseline

Usage:
  bun run src/main.tsx [options]

Options:
  --snapshot   Print the deterministic shell and exit without a renderer
  --ascii      Use printable ASCII borders
  --no-color   Disable color selection
  --help       Show this help
`;

export type CliDependencies = {
  write: (text: string) => void;
  runInteractive: (options: { ascii: boolean; noColor: boolean }) => Promise<void>;
};

export async function runCli(
  args: string[],
  dependencies: CliDependencies,
): Promise<number> {
  const known = new Set(["--snapshot", "--ascii", "--no-color", "--help"]);
  const unknown = args.find((arg) => !known.has(arg));
  if (unknown) {
    dependencies.write(`Unknown option: ${unknown}\n${HELP}`);
    return 2;
  }

  if (args.includes("--help")) {
    dependencies.write(HELP);
    return 0;
  }

  const options = {
    ascii: args.includes("--ascii"),
    noColor: args.includes("--no-color"),
  };
  if (args.includes("--snapshot")) {
    const model = buildShellViewModel(selectTerminalProfile(options));
    dependencies.write(renderShellSnapshot(model));
    return 0;
  }

  await dependencies.runInteractive(options);
  return 0;
}
