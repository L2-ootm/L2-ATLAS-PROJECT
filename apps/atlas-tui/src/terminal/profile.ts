export type TerminalProfile = {
  unicode: boolean;
  color: boolean;
};

export type TerminalProfileOptions = {
  ascii: boolean;
  noColor: boolean;
};

export function selectTerminalProfile(
  options: TerminalProfileOptions,
): TerminalProfile {
  return {
    unicode: !options.ascii,
    color: !options.noColor,
  };
}
