// ATLAS wordmark — shares the block-letter face used by services/atlas-tui
// (internal/tui/theme.go unicodeLogoRows) so both TUI surfaces present the
// same identity. `right` is intentionally blank: the wordmark now lives
// entirely in `left`, leaving the second column free for a caption.
export const logo = {
  left: [
    "                                           ",
    "                                           ",
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
    "                  ",
    "                  ",
    "█▀▀█ ▀▀█▀▀ █   █▀▀█ █▀▀▀",
    "█▄▄█   █   █   █▄▄█ ▀▀▀█",
    "█  █   █   █▄▄█ █  █ █▄▄█",
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
