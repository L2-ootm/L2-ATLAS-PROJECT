import { useMemo, useState, type CSSProperties } from 'react';
import { Check, Copy, FileText } from 'lucide-react';
import { ChatMarkdown } from './ChatMarkdown';
import { extensionOf, getHighlighter, languageForPath } from '../lib/highlightLanguages';

// InlineFileViewer — renders `read`-tool output (Console.tsx's ToolCallCard)
// as a syntax-highlighted, collapsible file preview instead of a raw <pre>
// dump. Reuses the same L2 Dark Prism tokens as ChatMarkdown's CodeBlock
// (dark translucent panel, hairline borders, --l2-font-mono) so it reads as
// part of the same visual system rather than a bolted-on widget.

const MARKDOWN_EXTENSIONS = new Set(['md', 'mdx']);

/** Binary-content guard: samples the first ~1KB. A null byte anywhere in the
 * sample is a hard binary signal; otherwise a high ratio of non-printable
 * control characters (excluding tab/LF/CR) indicates binary data. Keeps the
 * viewer from attempting to highlight/render content that isn't text. */
export function looksBinary(content: string): boolean {
	const sample = content.slice(0, 1024);
	if (sample.length === 0) return false;
	let nonPrintable = 0;
	for (let i = 0; i < sample.length; i++) {
		const code = sample.charCodeAt(i);
		if (code === 0) return true;
		if (code < 32 && code !== 9 && code !== 10 && code !== 13) {
			nonPrintable++;
		}
	}
	return nonPrintable / sample.length > 0.3;
}

const wrapStyle: CSSProperties = {
	position: 'relative',
	margin: 0,
	borderRadius: 2,
	border: '1px solid rgba(237,234,224,0.10)',
	overflow: 'hidden',
	background: 'rgba(13,16,24,0.55)'
};

const headerStyle: CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8,
	padding: '6px 10px',
	borderBottom: '1px solid rgba(237,234,224,0.08)',
	background: 'rgba(5,6,10,0.5)'
};

const pathStyle: CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	color: 'var(--l2-fg-2)',
	overflow: 'hidden',
	textOverflow: 'ellipsis',
	whiteSpace: 'nowrap',
	flex: '1 1 auto',
	minWidth: 0
};

const badgeStyle: CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.1em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-3)',
	border: '1px solid rgba(237,234,224,0.14)',
	borderRadius: 2,
	padding: '1px 6px',
	flex: '0 0 auto'
};

const copyButtonStyle: CSSProperties = {
	flex: '0 0 auto',
	width: 22,
	height: 22,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	borderRadius: 2,
	border: '1px solid rgba(237,234,224,0.14)',
	background: 'rgba(13,16,24,0.75)',
	color: 'var(--l2-fg-3)',
	cursor: 'pointer'
};

const bodyPreStyle: CSSProperties = {
	margin: 0,
	maxHeight: 480,
	overflow: 'auto',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 12,
	lineHeight: 1.55,
	padding: '10px 12px',
	background: 'rgba(5,6,10,0.65)',
	whiteSpace: 'pre',
	color: 'var(--l2-fg-1)'
};

const markdownBodyStyle: CSSProperties = {
	padding: '10px 12px',
	background: 'rgba(5,6,10,0.65)',
	maxHeight: 480,
	overflow: 'auto'
};

const binaryPlaceholderStyle: CSSProperties = {
	padding: '16px 12px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	color: 'var(--l2-fg-3)',
	textAlign: 'center',
	background: 'rgba(5,6,10,0.65)'
};

const toggleButtonStyle: CSSProperties = {
	display: 'block',
	width: '100%',
	padding: '6px 10px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	letterSpacing: '0.06em',
	color: 'var(--atlas-celestial)',
	background: 'rgba(74,93,191,0.10)',
	border: 'none',
	borderTop: '1px solid rgba(237,234,224,0.08)',
	cursor: 'pointer',
	textAlign: 'center'
};

export function InlineFileViewer({
	filePath,
	content,
	language,
	maxCollapsedLines = 40
}: {
	filePath: string;
	content: string;
	language?: string;
	maxCollapsedLines?: number;
}) {
	const [collapsed, setCollapsed] = useState(true);
	const [copied, setCopied] = useState(false);

	const ext = useMemo(() => extensionOf(filePath), [filePath]);
	const isMarkdown = MARKDOWN_EXTENSIONS.has(ext);
	const resolvedLanguage = language ?? languageForPath(filePath) ?? undefined;
	const isBinary = useMemo(() => looksBinary(content), [content]);

	const lines = useMemo(() => (content ? content.split('\n') : []), [content]);
	const canCollapse = lines.length > maxCollapsedLines;
	const shouldCollapse = collapsed && canCollapse;
	// Collapse operates on the raw text BEFORE highlighting — slice lines
	// first, then highlight only the sliced text. Highlighting the full file
	// and truncating the resulting HTML risks cutting mid-span and leaving
	// unclosed hljs-* tags.
	const displayContent = shouldCollapse ? lines.slice(0, maxCollapsedLines).join('\n') : content;
	const hiddenLineCount = lines.length - maxCollapsedLines;

	const highlightedHtml = useMemo(() => {
		if (isBinary || isMarkdown || !resolvedLanguage) return null;
		try {
			const hljs = getHighlighter();
			return hljs.highlight(displayContent, { language: resolvedLanguage }).value;
		} catch {
			return null;
		}
	}, [isBinary, isMarkdown, resolvedLanguage, displayContent]);

	const handleCopy = () => {
		if (!content) return;
		void navigator.clipboard
			?.writeText(content)
			.then(() => {
				setCopied(true);
				window.setTimeout(() => setCopied(false), 1400);
			})
			.catch(() => {});
	};

	const displayPath = filePath || 'file';
	const badgeText = isBinary ? 'BINARY' : (resolvedLanguage ?? ext ?? 'text').toUpperCase();

	return (
		<div style={wrapStyle}>
			<div style={headerStyle}>
				<FileText size={13} strokeWidth={1.7} style={{ color: 'var(--atlas-celestial)', flex: '0 0 auto' }} />
				<span style={pathStyle} title={displayPath}>
					{displayPath}
				</span>
				<span style={badgeStyle}>{badgeText}</span>
				<button
					type="button"
					onClick={handleCopy}
					style={copyButtonStyle}
					title={copied ? 'Copied' : 'Copy file'}
					aria-label={copied ? 'Copied' : 'Copy file'}
				>
					{copied ? <Check size={12} strokeWidth={1.8} /> : <Copy size={12} strokeWidth={1.8} />}
				</button>
			</div>
			{isBinary ? (
				<div style={binaryPlaceholderStyle}>Binary content — preview not available</div>
			) : isMarkdown ? (
				<div style={markdownBodyStyle}>
					<ChatMarkdown text={displayContent} style={{ fontSize: 12.5 }} />
				</div>
			) : highlightedHtml != null ? (
				<pre style={bodyPreStyle}>
					<code
						className={`hljs language-${resolvedLanguage}`}
						// Safe: highlight.js core's `highlight()` HTML-escapes the
						// source text before wrapping it in hljs-* spans (verified
						// against `<script>`/`&`/`<`/`>` content — see
						// InlineFileViewer.test.tsx's XSS-safety case).
						dangerouslySetInnerHTML={{ __html: highlightedHtml }}
					/>
				</pre>
			) : (
				<pre style={bodyPreStyle}>{displayContent}</pre>
			)}
			{canCollapse && (
				<button type="button" style={toggleButtonStyle} onClick={() => setCollapsed((v) => !v)}>
					{collapsed ? `Show ${hiddenLineCount} more line${hiddenLineCount === 1 ? '' : 's'}` : 'Show less'}
				</button>
			)}
		</div>
	);
}
