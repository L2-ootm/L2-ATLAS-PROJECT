// ATLAS wordmark — shares the block-letter face used by services/atlas-tui
// (internal/tui/theme.go unicodeLogoRows) so both TUI surfaces present the
// same identity. `right` is intentionally blank: the wordmark now lives
// entirely in `left`, leaving the second column free for a caption.
// Every row in a shape's `left` (and `right`) MUST be the same width: the
// renderer derives the right-column offset from row 0 and joins rows 1:1, so
// a single ragged row shifts glyphs sideways on screen (the 2026-07-11 UAT
// "ATLAS name looks misaligned" defect was exactly this).
export const logo = {
  left: [
    "                                          ",
    "                                          ",
    " █████╗ ████████╗██╗      █████╗ ███████╗ ",
    "██╔══██╗╚══██╔══╝██║     ██╔══██╗██╔════╝ ",
    "███████║   ██║   ██║     ███████║███████╗ ",
    "██╔══██║   ██║   ██║     ██╔══██║╚════██║ ",
    "██║  ██║   ██║   ███████╗██║  ██║███████║ ",
    "╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝ ",
  ],
  right: [
    "                    TERMINAL",
    "                            ",
    "                            ",
    "                            ",
    "                            ",
    "                            ",
    "                            ",
    "                            ",
  ],
}

export const logoThin = {
  left: [
    "                         ",
    "                         ",
    "█▀▀█ ▀▀█▀▀ █    █▀▀█ █▀▀▀",
    "█▄▄█   █   █    █▄▄█ ▀▀▀█",
    "█  █   █   █▄▄▄ █  █ ▄▄▄█",
  ],
  right: [
    "        TERMINAL",
    "                ",
    "                ",
    "                ",
    "                ",
  ],
}

export const logos = {
  thin: logoThin,
  classic: logo,
} as const

export type LogoKey = keyof typeof logos

export const go = {
  left: ["    ", "█▀▀█", "█  █", "▀▀▀▀"],
  right: ["    ", "█▀▀▀", "█ __", "▀▀▀▀"],
}

export const marks = "_^~,"
