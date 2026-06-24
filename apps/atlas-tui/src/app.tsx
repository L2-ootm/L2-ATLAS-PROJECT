import { useKeyboard } from "@opentui/solid";

import type { ShellViewModel } from "./view-model";

type AppProps = {
  model: ShellViewModel;
  onExit: () => void;
};

export function App(props: AppProps) {
  useKeyboard((key) => {
    if (key.ctrl && key.name === "c") {
      key.preventDefault();
      props.onExit();
    }
  });

  return (
    <box
      border
      borderStyle="single"
      borderColor="#8f7cff"
      flexDirection="column"
      gap={1}
      padding={1}
      title=" ATLAS "
      width="100%"
      height="100%"
    >
      <text>{props.model.mark}</text>
      <text>{props.model.workspace}</text>
      <text>{props.model.agent}</text>
      <text>{props.model.mode}</text>
      <box flexGrow={1} border borderStyle="single" title=" Transcript ">
        <text>{props.model.transcript}</text>
      </box>
      <box border borderStyle="single" title=" Composer ">
        <text>{`> ${props.model.composerPlaceholder}`}</text>
      </box>
      <text>{props.model.exitHint}</text>
    </box>
  );
}
