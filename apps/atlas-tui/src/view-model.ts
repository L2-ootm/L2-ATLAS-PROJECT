import type { TerminalProfile } from "./terminal/profile";
import { ATLAS_MARK } from "./brand/atlas-mark";

export type ShellViewModel = {
  profile: TerminalProfile;
  mark: string;
  workspace: string;
  agent: string;
  mode: string;
  transcript: string;
  composerPlaceholder: string;
  exitHint: string;
};

export function buildShellViewModel(profile: TerminalProfile): ShellViewModel {
  return {
    profile,
    mark: ATLAS_MARK,
    workspace: "Workspace: not connected",
    agent: "Agent: not connected",
    mode: "Mode: intake baseline",
    transcript: "",
    composerPlaceholder: "Type a message after ATLAS contracts are connected",
    exitHint: "Ctrl-C to exit",
  };
}

export function renderShellSnapshot(model: ShellViewModel): string {
  const border = model.profile.unicode
    ? {
        top: "┌────────────────────────────────────────────────────────────┐",
        side: "│",
        bottom: "└────────────────────────────────────────────────────────────┘",
      }
    : {
        top: "+------------------------------------------------------------+",
        side: "|",
        bottom: "+------------------------------------------------------------+",
      };
  const row = (value: string) =>
    `${border.side} ${value.padEnd(58, " ")} ${border.side}`;

  return [
    border.top,
    row(model.mark),
    row(""),
    row(model.workspace),
    row(model.agent),
    row(model.mode),
    row(""),
    row(model.transcript),
    row(""),
    row(`> ${model.composerPlaceholder}`),
    row(""),
    row(model.exitHint),
    border.bottom,
    "",
  ].join("\n");
}
