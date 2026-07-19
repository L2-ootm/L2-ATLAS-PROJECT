import hljsCore from 'highlight.js/lib/core';
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
import type { LanguageFn } from 'highlight.js';
import type { Options as RehypeHighlightOptions } from 'rehype-highlight';

// Shared curated language registry — deliberately a small subset (not
// rehype-highlight's default `common` grammar bundle, which pulls ~37
// languages via lowlight) to keep the vendor-markdown chunk under the
// project's bundle budget (see scripts/check-bundle-budget.mjs).
//
// Two consumers:
//  - ChatMarkdown.tsx passes `highlightLanguages`/`highlightAliases` as
//    rehype-highlight options (react-markdown pipeline, powered by lowlight
//    internally).
//  - InlineFileViewer.tsx highlights raw tool-output text standalone (no
//    markdown AST involved), via `getHighlighter()` — a highlight.js `core`
//    instance with the same grammars registered directly. highlight.js core's
//    `highlight()` HTML-escapes the source before wrapping it in `hljs-*`
//    spans, so `dangerouslySetInnerHTML` of its output is safe for arbitrary
//    file content (verified: `<script>`, `&`, `<`, `>` all come back escaped).
export const highlightLanguages: Record<string, LanguageFn> = {
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

export const highlightAliases: RehypeHighlightOptions['aliases'] = {
	javascript: ['js', 'jsx'],
	typescript: ['ts', 'tsx'],
	bash: ['sh', 'shell', 'zsh'],
	yaml: ['yml'],
	xml: ['html']
};

let registered = false;

/** Lazily registers the curated grammar set on a highlight.js `core` instance
 * and returns it. Safe to call repeatedly (registerLanguage is idempotent). */
export function getHighlighter(): typeof hljsCore {
	if (!registered) {
		for (const [name, lang] of Object.entries(highlightLanguages)) {
			hljsCore.registerLanguage(name, lang);
		}
		registered = true;
	}
	return hljsCore;
}

// File-extension -> canonical registered language name. Mirrors
// highlightAliases plus a few extra extensions common in tool output that
// rehype-highlight's fence-language aliasing doesn't need to know about.
const EXTENSION_LANGUAGE_MAP: Record<string, string> = {
	sh: 'bash',
	bash: 'bash',
	zsh: 'bash',
	c: 'c',
	h: 'c',
	cpp: 'cpp',
	cc: 'cpp',
	cxx: 'cpp',
	hpp: 'cpp',
	hh: 'cpp',
	cs: 'csharp',
	css: 'css',
	scss: 'css',
	less: 'css',
	diff: 'diff',
	patch: 'diff',
	go: 'go',
	java: 'java',
	js: 'javascript',
	jsx: 'javascript',
	mjs: 'javascript',
	cjs: 'javascript',
	json: 'json',
	jsonc: 'json',
	md: 'markdown',
	mdx: 'markdown',
	py: 'python',
	pyi: 'python',
	rs: 'rust',
	sql: 'sql',
	ts: 'typescript',
	tsx: 'typescript',
	xml: 'xml',
	html: 'xml',
	htm: 'xml',
	svg: 'xml',
	yaml: 'yaml',
	yml: 'yaml'
};

/** Extracts the lowercased extension (no dot) from a file path, ignoring any
 * directory separators. Returns '' if there is none. */
export function extensionOf(filePath: string): string {
	const base = filePath.split(/[\\/]/).pop() ?? filePath;
	const match = /\.([a-z0-9]+)$/i.exec(base);
	return match ? match[1].toLowerCase() : '';
}

/** Maps a file path to one of the registered language names, or null if the
 * extension isn't recognized. */
export function languageForPath(filePath: string): string | null {
	const ext = extensionOf(filePath);
	return ext ? (EXTENSION_LANGUAGE_MAP[ext] ?? null) : null;
}
