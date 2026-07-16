import {
	useRef,
	useState,
	type CSSProperties,
	type ComponentPropsWithoutRef,
	type JSX,
	type ReactNode
} from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight, { type Options as RehypeHighlightOptions } from 'rehype-highlight';
import bash from 'highlight.js/lib/languages/bash';
import c from 'highlight.js/lib/languages/c';
import cpp from 'highlight.js/lib/languages/cpp';
import csharp from 'highlight.js/lib/languages/csharp';
import css from 'highlight.js/lib/languages/css';
import diff from 'highlight.js/lib/languages/diff';
import go from 'highlight.js/lib/languages/go';
import java from 'highlight.js/lib/languages/java';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import markdown from 'highlight.js/lib/languages/markdown';
import python from 'highlight.js/lib/languages/python';
import rust from 'highlight.js/lib/languages/rust';
import sql from 'highlight.js/lib/languages/sql';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';
import { Check, Copy } from 'lucide-react';

// ChatMarkdown — renders agent/operator prose (chat text, turn text events,
// tool-result prose) as intentional dark-terminal markdown. Reuses the L2
// Dark Prism token set (see Console.tsx's monoLabelStyle/toolCardStyle
// family) rather than any default browser or Tailwind markdown styling.
//
// Language set is a deliberately small, curated subset — not rehype-highlight's
// default `common` grammar bundle (37 languages via lowlight) — to keep the
// vendor-markdown chunk under the project's bundle budget (see
// scripts/check-bundle-budget.mjs).
const highlightLanguages: RehypeHighlightOptions['languages'] = {
	bash,
	c,
	cpp,
	csharp,
	css,
	diff,
	go,
	java,
	javascript,
	json,
	markdown,
	python,
	rust,
	sql,
	typescript,
	xml,
	yaml
};

const highlightAliases: RehypeHighlightOptions['aliases'] = {
	javascript: ['js', 'jsx'],
	typescript: ['ts', 'tsx'],
	bash: ['sh', 'shell', 'zsh'],
	yaml: ['yml'],
	xml: ['html']
};

const proseStyle: CSSProperties = {
	color: 'var(--l2-fg-1)',
	fontSize: 13.5,
	lineHeight: 1.58,
	overflowWrap: 'anywhere'
};

const paragraphStyle: CSSProperties = {
	margin: '0 0 8px',
	whiteSpace: 'pre-wrap'
};

function headingStyle(size: number): CSSProperties {
	return {
		margin: '14px 0 6px',
		fontSize: size,
		fontWeight: 600,
		lineHeight: 1.35,
		color: 'var(--l2-fg-0, var(--l2-fg-1))'
	};
}

const listStyle: CSSProperties = {
	margin: '0 0 8px',
	paddingLeft: 20,
	display: 'flex',
	flexDirection: 'column',
	gap: 3
};

const linkStyle: CSSProperties = {
	color: 'var(--atlas-celestial)',
	textDecoration: 'underline',
	textUnderlineOffset: 2
};

const inlineCodeStyle: CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: '0.92em',
	color: 'var(--atlas-celestial)',
	background: 'rgba(74,93,191,0.14)',
	border: '1px solid rgba(74,93,191,0.28)',
	borderRadius: 2,
	padding: '1px 4px'
};

const blockquoteStyle: CSSProperties = {
	margin: '0 0 8px',
	padding: '2px 12px',
	borderLeft: '2px solid rgba(74,93,191,0.45)',
	color: 'var(--l2-fg-2)'
};

const hrStyle: CSSProperties = {
	border: 'none',
	borderTop: '1px solid rgba(237,234,224,0.10)',
	margin: '10px 0'
};

const tableWrapStyle: CSSProperties = {
	overflowX: 'auto',
	margin: '0 0 8px',
	border: '1px solid rgba(237,234,224,0.08)',
	borderRadius: 2
};

const tableStyle: CSSProperties = {
	borderCollapse: 'collapse',
	width: '100%',
	fontSize: 12.5
};

const thStyle: CSSProperties = {
	textAlign: 'left',
	padding: '6px 9px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	letterSpacing: '0.08em',
	color: 'var(--l2-fg-2)',
	background: 'rgba(13,16,24,0.65)',
	borderBottom: '1px solid rgba(237,234,224,0.10)'
};

const tdStyle: CSSProperties = {
	padding: '6px 9px',
	borderBottom: '1px solid rgba(237,234,224,0.06)',
	verticalAlign: 'top'
};

const codeBlockWrapStyle: CSSProperties = {
	position: 'relative',
	margin: '0 0 8px',
	borderRadius: 2,
	border: '1px solid rgba(237,234,224,0.08)',
	overflow: 'hidden'
};

const codeBlockPreStyle: CSSProperties = {
	margin: 0,
	maxHeight: 480,
	overflow: 'auto',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 12,
	lineHeight: 1.55,
	padding: '10px 12px',
	background: 'rgba(5,6,10,0.65)',
	whiteSpace: 'pre'
};

const copyButtonStyle: CSSProperties = {
	position: 'absolute',
	top: 6,
	right: 6,
	width: 24,
	height: 24,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	borderRadius: 2,
	border: '1px solid rgba(237,234,224,0.14)',
	background: 'rgba(13,16,24,0.75)',
	color: 'var(--l2-fg-3)',
	cursor: 'pointer'
};

// react-markdown passes an extra `node` (hast node) prop to every custom
// component (it renders with `passNode: true`); it must never reach a real
// DOM element or React warns about an unrecognized attribute. Every override
// below strips it via this one helper instead of destructuring-and-discarding
// `node` at each call site.
type MdProps<Tag extends keyof JSX.IntrinsicElements> = ComponentPropsWithoutRef<Tag> & {
	node?: unknown;
};

function omitNode<Tag extends keyof JSX.IntrinsicElements>(
	props: MdProps<Tag>
): ComponentPropsWithoutRef<Tag> {
	const rest = { ...props };
	delete rest.node;
	return rest;
}

function CodeBlock(fullProps: MdProps<'pre'>) {
	const { children, ...rest } = omitNode(fullProps);
	const preRef = useRef<HTMLPreElement>(null);
	const [copied, setCopied] = useState(false);

	const handleCopy = () => {
		const text = preRef.current?.textContent ?? '';
		if (!text) return;
		void navigator.clipboard
			?.writeText(text)
			.then(() => {
				setCopied(true);
				window.setTimeout(() => setCopied(false), 1400);
			})
			.catch(() => {});
	};

	return (
		<div style={codeBlockWrapStyle}>
			<button
				type="button"
				onClick={handleCopy}
				style={copyButtonStyle}
				title={copied ? 'Copied' : 'Copy code'}
				aria-label={copied ? 'Copied' : 'Copy code'}
			>
				{copied ? <Check size={12} strokeWidth={1.8} /> : <Copy size={12} strokeWidth={1.8} />}
			</button>
			<pre ref={preRef} {...rest} style={codeBlockPreStyle}>
				{children}
			</pre>
		</div>
	);
}

function InlineOrBlockCode(fullProps: MdProps<'code'>) {
	const { className, children, ...rest } = omitNode(fullProps);
	// rehype-highlight only assigns a className (hljs + language-*) to fenced
	// code blocks (the `pre > code` case); inline `code` spans stay bare.
	if (!className) {
		return (
			<code style={inlineCodeStyle} {...rest}>
				{children}
			</code>
		);
	}
	return (
		<code className={className} {...rest}>
			{children}
		</code>
	);
}

const markdownComponents: Components = {
	p: (props: MdProps<'p'>) => <p style={paragraphStyle} {...omitNode(props)} />,
	h1: (props: MdProps<'h1'>) => <h1 style={headingStyle(18)} {...omitNode(props)} />,
	h2: (props: MdProps<'h2'>) => <h2 style={headingStyle(16.5)} {...omitNode(props)} />,
	h3: (props: MdProps<'h3'>) => <h3 style={headingStyle(15)} {...omitNode(props)} />,
	h4: (props: MdProps<'h4'>) => <h4 style={headingStyle(13.5)} {...omitNode(props)} />,
	h5: (props: MdProps<'h5'>) => <h5 style={headingStyle(13)} {...omitNode(props)} />,
	h6: (props: MdProps<'h6'>) => <h6 style={headingStyle(12.5)} {...omitNode(props)} />,
	ul: (props: MdProps<'ul'>) => <ul style={{ ...listStyle, listStyleType: 'disc' }} {...omitNode(props)} />,
	ol: (props: MdProps<'ol'>) => <ol style={{ ...listStyle, listStyleType: 'decimal' }} {...omitNode(props)} />,
	li: (props: MdProps<'li'>) => <li style={{ margin: 0 }} {...omitNode(props)} />,
	a: (props: MdProps<'a'>) => (
		<a style={linkStyle} target="_blank" rel="noreferrer noopener" {...omitNode(props)} />
	),
	blockquote: (props: MdProps<'blockquote'>) => <blockquote style={blockquoteStyle} {...omitNode(props)} />,
	hr: (props: MdProps<'hr'>) => <hr style={hrStyle} {...omitNode(props)} />,
	strong: (props: MdProps<'strong'>) => (
		<strong style={{ color: 'inherit', fontWeight: 700 }} {...omitNode(props)} />
	),
	table: (props: MdProps<'table'>) => (
		<div style={tableWrapStyle}>
			<table style={tableStyle} {...omitNode(props)} />
		</div>
	),
	thead: (props: MdProps<'thead'>) => <thead {...omitNode(props)} />,
	th: (props: MdProps<'th'>) => <th style={thStyle} {...omitNode(props)} />,
	td: (props: MdProps<'td'>) => <td style={tdStyle} {...omitNode(props)} />,
	pre: CodeBlock,
	code: InlineOrBlockCode
};

export function ChatMarkdown({ text, style }: { text: string; style?: CSSProperties }): ReactNode {
	return (
		<div style={style ? { ...proseStyle, ...style } : proseStyle}>
			<ReactMarkdown
				remarkPlugins={[remarkGfm]}
				rehypePlugins={[[rehypeHighlight, { languages: highlightLanguages, aliases: highlightAliases }]]}
				components={markdownComponents}
			>
				{text}
			</ReactMarkdown>
		</div>
	);
}
