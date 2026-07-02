package tui

// Transcript model: the conversation is a list of typed items rendered at
// view time against the current terminal width. Storing semantics instead of
// pre-styled strings is what lets long assistant responses wrap correctly,
// resize re-flow, and tool calls update in place (running -> done/failed) —
// the opencode/MiMo block hierarchy, ATLAS-native.

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

type itemKind int

const (
	itemUser itemKind = iota
	itemAssistant
	itemReasoning
	itemTool
	itemRetrieval
	itemDiff
	itemError
	itemSystem // dim informational line
	itemNotice // positive confirmation line
	itemRule   // run/turn boundary
)

type transcriptItem struct {
	kind   itemKind
	label  string // tool name, rule caption
	text   string // main body, unstyled
	detail string // secondary inline detail
	status string // tool lifecycle: "running" | "done" | "failed"
	callID string // audit tool_call_id for in-place completion
}

// renderTranscript renders all items wrapped to width, with block spacing:
// conversation blocks (user/assistant/reasoning/error) breathe; activity
// lines (tools, retrieval, diffs) stay dense.
func renderTranscript(items []transcriptItem, width int) string {
	if width < 20 {
		width = 20
	}
	var out []string
	for i, it := range items {
		rendered := renderItem(it, width)
		if rendered == "" {
			continue
		}
		if len(out) > 0 && blockSpacing(items, i) {
			out = append(out, "")
		}
		out = append(out, rendered)
	}
	return strings.Join(out, "\n")
}

func blockSpacing(items []transcriptItem, i int) bool {
	switch items[i].kind {
	case itemUser, itemAssistant, itemReasoning, itemError, itemRule:
		return true
	default:
		// First activity line after a text block gets a separating breath.
		if i > 0 {
			switch items[i-1].kind {
			case itemUser, itemAssistant, itemReasoning, itemError:
				return true
			}
		}
		return false
	}
}

func renderItem(it transcriptItem, width int) string {
	switch it.kind {
	case itemUser:
		return renderUserItem(it, width)
	case itemAssistant:
		return renderAssistantItem(it, width)
	case itemReasoning:
		return renderReasoningItem(it, width)
	case itemTool:
		return renderToolItem(it, width)
	case itemRetrieval:
		return styleVioletStyle.Render(
			truncate(gl.bullet+" retrieval "+safeInline(joinNonEmpty(it.text, it.detail), 200), width),
		)
	case itemDiff:
		return styleWarn.Render(truncate(gl.diffMark+" "+safeInline(joinNonEmpty(it.text, it.detail), 200), width))
	case itemError:
		return renderErrorItem(it, width)
	case itemSystem:
		return styleMuted.Render(wordWrap(safeInline(it.text, 500), width))
	case itemNotice:
		return styleGood.Render(truncate(safeInline(it.text, 300), width))
	case itemRule:
		return renderRuleItem(it, width)
	default:
		return ""
	}
}

func renderUserItem(it transcriptItem, width int) string {
	bar := styleVioletStyle.Render(gl.prompt)
	body := wordWrap(strings.TrimSpace(it.text), max(10, width-lipgloss.Width(gl.prompt)))
	var b strings.Builder
	for i, line := range strings.Split(body, "\n") {
		if i > 0 {
			b.WriteString("\n")
		}
		b.WriteString(bar + styleVal.Render(line))
	}
	return b.String()
}

func renderAssistantItem(it transcriptItem, width int) string {
	label := styleTitle.Render("ATLAS")
	return label + "\n" + markdownLite(it.text, width)
}

func renderReasoningItem(it transcriptItem, width int) string {
	label := styleMuted.Bold(true).Render("reasoning")
	body := wordWrap(strings.TrimSpace(it.text), max(10, width-2))
	var b strings.Builder
	b.WriteString(label)
	for _, line := range strings.Split(body, "\n") {
		b.WriteString("\n" + styleMuted.Render("  "+line))
	}
	return b.String()
}

func renderToolItem(it transcriptItem, width int) string {
	glyph := styleWarn.Render(gl.toolRun)
	switch it.status {
	case "done":
		glyph = styleGood.Render(gl.toolOK)
	case "failed":
		glyph = styleBad.Render(gl.toolBad)
	}
	name := orDash(it.label)
	detail := safeInline(joinNonEmpty(it.text, it.detail), 300)
	budget := width - lipgloss.Width(gl.toolRun) - len([]rune(name)) - 2
	if budget < 8 {
		budget = 8
	}
	detail = truncate(detail, budget)
	line := glyph + " " + styleKey.Render(name)
	if detail != "" {
		line += " " + styleMuted.Render(detail)
	}
	return line
}

func renderErrorItem(it transcriptItem, width int) string {
	label := styleBad.Bold(true).Render("ERROR")
	if it.label != "" {
		label += " " + styleBad.Render(it.label)
	}
	body := wordWrap(safeInline(it.text, 600), max(10, width-2))
	var b strings.Builder
	b.WriteString(label)
	for _, line := range strings.Split(body, "\n") {
		b.WriteString("\n" + styleBad.Render("  "+line))
	}
	return b.String()
}

func renderRuleItem(it transcriptItem, width int) string {
	caption := strings.TrimSpace(it.label)
	if caption == "" {
		caption = "run"
	}
	rule := gl.dash + gl.dash + " " + caption + " " + gl.dash + gl.dash
	style := styleMuted
	if it.status == "failed" {
		style = styleBad
	}
	return style.Render(truncate(rule, width))
}

// --- markdown-lite -----------------------------------------------------------
//
// Hand-rolled subset renderer (headings, bullets, fenced code, inline bold and
// code) so assistant responses read like a document without adding a markdown
// dependency. Anything unrecognized falls through as wrapped plain text.

func markdownLite(text string, width int) string {
	width = max(20, width)
	var out []string
	inFence := false
	for _, raw := range strings.Split(strings.ReplaceAll(text, "\r\n", "\n"), "\n") {
		line := strings.TrimRight(raw, " \t")
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "```") {
			inFence = !inFence
			out = append(out, styleCodeBlock.Render(gl.codeBar))
			continue
		}
		if inFence {
			out = append(out, styleCodeBlock.Render(gl.codeBar+truncate(line, width-2)))
			continue
		}
		switch {
		case trimmed == "":
			out = append(out, "")
		case strings.HasPrefix(trimmed, "#"):
			heading := strings.TrimSpace(strings.TrimLeft(trimmed, "#"))
			out = append(out, styleTitle.Render(truncate(heading, width)))
		case strings.HasPrefix(trimmed, "- ") || strings.HasPrefix(trimmed, "* "):
			body := strings.TrimSpace(trimmed[2:])
			wrapped := wordWrap(body, max(10, width-2))
			for i, wl := range strings.Split(wrapped, "\n") {
				prefix := gl.bullet + " "
				if i > 0 {
					prefix = "  "
				}
				out = append(out, prefix+styleInline(wl))
			}
		default:
			for _, wl := range strings.Split(wordWrap(trimmed, width), "\n") {
				out = append(out, styleInline(wl))
			}
		}
	}
	return strings.TrimRight(strings.Join(out, "\n"), "\n")
}

// styleInline applies **bold** and `code` spans; plain text renders as body.
func styleInline(line string) string {
	var b strings.Builder
	rest := line
	for {
		bold := strings.Index(rest, "**")
		code := strings.Index(rest, "`")
		if bold == -1 && code == -1 {
			b.WriteString(styleVal.Render(rest))
			return b.String()
		}
		if bold != -1 && (code == -1 || bold <= code) {
			end := strings.Index(rest[bold+2:], "**")
			if end == -1 {
				b.WriteString(styleVal.Render(rest))
				return b.String()
			}
			b.WriteString(styleVal.Render(rest[:bold]))
			b.WriteString(styleVal.Bold(true).Render(rest[bold+2 : bold+2+end]))
			rest = rest[bold+4+end:]
			continue
		}
		end := strings.Index(rest[code+1:], "`")
		if end == -1 {
			b.WriteString(styleVal.Render(rest))
			return b.String()
		}
		b.WriteString(styleVal.Render(rest[:code]))
		b.WriteString(styleCode.Render(rest[code+1 : code+1+end]))
		rest = rest[code+2+end:]
	}
}

// wordWrap is a minimal greedy wrapper (no external reflow dependency). It
// wraps on spaces and hard-splits tokens longer than the width.
func wordWrap(text string, width int) string {
	if width < 1 {
		width = 1
	}
	var lines []string
	for _, paragraph := range strings.Split(text, "\n") {
		words := strings.Fields(paragraph)
		if len(words) == 0 {
			lines = append(lines, "")
			continue
		}
		current := ""
		for _, word := range words {
			for len([]rune(word)) > width {
				runes := []rune(word)
				if current != "" {
					lines = append(lines, current)
					current = ""
				}
				lines = append(lines, string(runes[:width]))
				word = string(runes[width:])
			}
			switch {
			case current == "":
				current = word
			case len([]rune(current))+1+len([]rune(word)) <= width:
				current += " " + word
			default:
				lines = append(lines, current)
				current = word
			}
		}
		if current != "" {
			lines = append(lines, current)
		}
	}
	return strings.Join(lines, "\n")
}

func runFinishedRule(status string) transcriptItem {
	caption := "run " + orDash(status)
	item := transcriptItem{kind: itemRule, label: caption}
	if status != "succeeded" {
		item.status = "failed"
	}
	return item
}

func elapsedLabel(seconds int) string {
	if seconds < 60 {
		return fmt.Sprintf("%ds", seconds)
	}
	return fmt.Sprintf("%dm%02ds", seconds/60, seconds%60)
}
