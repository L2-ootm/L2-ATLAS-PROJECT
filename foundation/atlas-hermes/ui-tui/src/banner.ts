import type { ThemeColors } from './theme.js'

const RICH_RE = /\[(?:bold\s+)?(?:dim\s+)?(#(?:[0-9a-fA-F]{3,8}))\]([\s\S]*?)(\[\/\])/g

export function parseRichMarkup(markup: string): Line[] {
  const lines: Line[] = []

  for (const raw of markup.split('\n')) {
    const trimmed = raw.trimEnd()

    if (!trimmed) {
      lines.push(['', ' '])

      continue
    }

    const matches = [...trimmed.matchAll(RICH_RE)]

    if (!matches.length) {
      lines.push(['', trimmed])

      continue
    }

    let cursor = 0

    for (const m of matches) {
      const before = trimmed.slice(cursor, m.index)

      if (before) {
        lines.push(['', before])
      }

      lines.push([m[1]!, m[2]!])
      cursor = m.index! + m[0].length
    }

    if (cursor < trimmed.length) {
      lines.push(['', trimmed.slice(cursor)])
    }
  }

  return lines
}

// ── ATLAS Wordmark ────────────────────────────────────────────────────
// Thin-stroke engraved letterforms — small slab serifs, open counters,
// echoing the Cinzel display typeface. Architectural, not blocky.
// Each letter is built from thin strokes (═, ─, │) and small serifs
// (╔, ╗, ╚, ╝, ╦, ╩, ╠, ╣) to evoke metal engraving.

const LOGO_ART = [
  '  ╔═╗ ╔═╗ ╔╦╗ ╔═╗ ╔═╗ ╔═╗ ╔═╗  ',
  '  ║╣  ╚═╗  ║║ ║ ║ ║ ║ ║╣  ╚═╗  ',
  ' ╚═╝ ╚═╝ ═╩╝ ╚═╝ ╚═╝ ╚═╝ ╚═╝  ',
]

// ── ATLAS Celestial Mark ──────────────────────────────────────────────
// Astrolabe globe with constellation linework, compass star apex,
// and bronze bearer cradle. Draws from the Operator-Atlas emblem:
// titan bearing a constellation globe over a circuit temple.
//
// Characters: ╭╮╰╯ globe rim, ─│ graticule, · constellation nodes,
// ╱╲ cradle arcs, ◆ compass star / cradle terminals.

const CADUCEUS_ART = [
  '           ◆           ',
  '          ╱│╲          ',
  '         ╱ │ ╲         ',
  '        ╱  │  ╲        ',
  '       ╱ ·─┼─· ╲       ',
  '      ╱    │    ╲      ',
  '     ╱  ·──┼──·  ╲     ',
  '    │      │      │    ',
  '     ╲  ·──┼──·  ╱     ',
  '      ╲    │    ╱      ',
  '       ╲ ·─┼─· ╱       ',
  '        ╲  │  ╱        ',
  '         ╲ │ ╱         ',
  '          ╲│╱          ',
  '       ◆───┴───◆       ',
]

// Gradient maps line index → palette slot [primary, accent, border, muted].
const LOGO_GRADIENT = [1, 0, 1] as const
const CADUC_GRADIENT = [
  1, // compass star
  0, 0, 0, // upper globe
  1, // crosshairs + nodes
  0, // equator
  1, // crosshairs + nodes
  2, // lower globe
  1, // crosshairs + nodes
  0, // lower globe
  1, // crosshairs + nodes
  0, // lower rim
  0, // lower rim
  2, // cradle converge
  2, // cradle base
] as const

const colorize = (art: string[], gradient: readonly number[], c: ThemeColors): Line[] => {
  const p = [c.primary, c.accent, c.border, c.muted]

  return art.map((text, i) => [p[gradient[i]!] ?? c.muted, text])
}

export const LOGO_WIDTH = Math.max(...LOGO_ART.map(line => line.length))
export const CADUCEUS_WIDTH = Math.max(...CADUCEUS_ART.map(line => line.length))

export const logo = (c: ThemeColors, customLogo?: string): Line[] =>
  customLogo ? parseRichMarkup(customLogo) : colorize(LOGO_ART, LOGO_GRADIENT, c)

export const caduceus = (c: ThemeColors, customHero?: string): Line[] =>
  customHero ? parseRichMarkup(customHero) : colorize(CADUCEUS_ART, CADUC_GRADIENT, c)

export const artWidth = (lines: Line[]) => lines.reduce((m, [, t]) => Math.max(m, t.length), 0)

type Line = [string, string]
