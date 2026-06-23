import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, FileText } from 'lucide-react';
import { Page } from '../components/Page';
import TopoInput from '../components/TopoInput';
import { glassPanel } from '../lib/glass';
import {
	listWikiPages,
	searchWiki,
	getWikiPage,
	type WikiPage,
	type WikiPageDetail,
	type WikiSearchResult
} from '../lib/api';
import { useGatewayHealth } from '../lib/useGatewayHealth';
import sealMark from '../brand/assets/seal.webp';

// ── Codex — /wiki — the memory/knowledge foundation ──────────────────────────
// Two-column browser: FTS search + page list (left) → markdown reading slab +
// provenance sidecar (right). All endpoints exist (HARNESS-WIRING §2): list,
// search, page-detail-with-provenance. Read-first; authoring stays in the CLI.

type ListLoad =
	| { s: 'loading' }
	| { s: 'ready'; pages: WikiPage[] }
	| { s: 'error' };

type PageLoad =
	| { s: 'idle' }
	| { s: 'loading' }
	| { s: 'ready'; page: WikiPageDetail }
	| { s: 'error' };

function rel(iso: string): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return '—';
	const d = (Date.now() - t) / 1000;
	if (d < 60) return 'just now';
	if (d < 3600) return `${Math.floor(d / 60)}m ago`;
	if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
	return `${Math.floor(d / 86400)}d ago`;
}

export default function Codex() {
	const [list, setList] = useState<ListLoad>({ s: 'loading' });
	const [results, setResults] = useState<WikiSearchResult[] | null>(null);
	const [query, setQuery] = useState('');
	const [slug, setSlug] = useState<string | null>(null);
	const [page, setPage] = useState<PageLoad>({ s: 'idle' });
	const { epoch } = useGatewayHealth();

	const refresh = useCallback(async () => {
		try {
			const { pages } = await listWikiPages(80);
			setList({ s: 'ready', pages });
		} catch {
			setList({ s: 'error' });
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh, epoch]);

	// Debounced FTS search; empty query clears back to the full list.
	useEffect(() => {
		const q = query.trim();
		if (q === '') {
			setResults(null);
			return;
		}
		const id = setTimeout(() => {
			void searchWiki(q, 40)
				.then(({ results }) => setResults(results))
				.catch(() => setResults([]));
		}, 220);
		return () => clearTimeout(id);
	}, [query]);

	const openPage = useCallback(async (s: string) => {
		setSlug(s);
		setPage({ s: 'loading' });
		try {
			const { page } = await getWikiPage(s);
			setPage({ s: 'ready', page });
		} catch {
			setPage({ s: 'error' });
		}
	}, []);

	const rows = useMemo(() => {
		if (results !== null) {
			return results.map((r) => ({ slug: r.slug, title: r.title, updated_at: r.updated_at, snippet: r.snippet }));
		}
		if (list.s === 'ready') {
			return list.pages.map((p) => ({ slug: p.slug, title: p.title, updated_at: p.updated_at, snippet: undefined as string | undefined }));
		}
		return [];
	}, [results, list]);

	const count = results !== null ? results.length : list.s === 'ready' ? list.pages.length : null;

	return (
		<Page
			eyebrow="STRUCTURE"
			title="Codex"
			actions={<span style={mono(11, 'var(--l2-fg-3)')}>{count === null ? '—' : `${count} PAGES`}</span>}
		>
			<div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 360px) 1fr', gap: 16, alignItems: 'start' }} className="atlas-codex-grid">
				{/* left — search + list */}
				<div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
					<TopoInput
						value={query}
						onChange={setQuery}
						placeholder="Search the codex…"
						ariaLabel="Search wiki"
						tone="info"
						icon={<Search size={15} strokeWidth={1.5} />}
					/>
					<section style={glassPanel({ overflow: 'hidden' })}>
						{list.s === 'loading' && <ListSkeleton />}
						{list.s === 'error' && <Offline />}
						{list.s === 'ready' && (
							rows.length === 0 ? (
								<div style={{ padding: '24px 16px', color: 'var(--l2-fg-3)', fontSize: 13 }}>
									{results !== null ? `No pages match “${query.trim()}”.` : 'No pages yet.'}
								</div>
							) : (
								<div style={{ maxHeight: '66vh', overflowY: 'auto' }}>
									{rows.map((r, i) => (
										<button
											key={r.slug}
											onClick={() => void openPage(r.slug)}
											data-topo="info"
											style={{
												display: 'block',
												width: '100%',
												textAlign: 'left',
												padding: '12px 16px',
												borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)',
												background: r.slug === slug ? 'rgba(79,139,255,0.08)' : 'transparent',
												border: 'none',
												borderLeft: r.slug === slug ? '2px solid var(--atlas-celestial)' : '2px solid transparent',
												cursor: 'pointer'
											}}
										>
											<div style={{ color: 'var(--l2-fg-1)', fontSize: 13.5, marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
												{r.title}
											</div>
											<div style={{ ...mono(10, 'var(--l2-fg-3)'), letterSpacing: '0.04em' }}>
												{r.slug} · {rel(r.updated_at)}
											</div>
											{r.snippet && (
												<div style={{ color: 'var(--l2-fg-3)', fontSize: 12, marginTop: 5, lineHeight: 1.5 }}>
													…{r.snippet}…
												</div>
											)}
										</button>
									))}
								</div>
							)
						)}
					</section>
				</div>

				{/* right — viewer + provenance */}
				<div style={{ minWidth: 0 }}>
					{page.s === 'idle' && <ViewerEmpty />}
					{page.s === 'loading' && <ViewerSkeleton />}
					{page.s === 'error' && <ViewerError slug={slug} />}
					{page.s === 'ready' && <Viewer page={page.page} />}
				</div>
			</div>
		</Page>
	);
}

// ── viewer ─────────────────────────────────────────────────────────────────────
function Viewer({ page }: { page: WikiPageDetail }) {
	return (
		<div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
			<article style={glassPanel({ padding: '28px 32px', position: 'relative', overflow: 'hidden' })}>
				<span aria-hidden="true" style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, var(--atlas-bronze) 50%, transparent)', opacity: 0.5 }} />
				<div style={{ ...mono(10, 'var(--l2-fg-3)'), letterSpacing: '0.18em', marginBottom: 8 }}>{page.slug}</div>
				<h2 style={{ fontFamily: 'var(--l2-font-serif)', fontWeight: 600, fontSize: 26, color: 'var(--l2-fg-1)', margin: '0 0 20px', lineHeight: 1.15 }}>
					{page.title}
				</h2>
				<Markdown body={page.body ?? ''} />
			</article>
			<ProvenancePanel page={page} />
		</div>
	);
}

function ProvenancePanel({ page }: { page: WikiPageDetail }) {
	const p = page.provenance;
	const rows: Array<[string, string]> = [
		['Run', p?.run_id ?? '—'],
		['Operator', p?.operator_id ?? '—'],
		['Source', p?.source_id ?? '—'],
		['Sensitivity', p?.sensitivity ?? '—'],
		['Written', p?.written_at ?? page.updated_at]
	];
	return (
		<section style={glassPanel({ overflow: 'hidden' })}>
			<header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 18px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<FileText size={13} strokeWidth={1.6} color="var(--atlas-bronze)" />
				<span style={{ ...mono(10.5, 'var(--atlas-bronze)'), letterSpacing: '0.2em' }}>PROVENANCE</span>
			</header>
			<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
				{rows.map(([k, v], i) => (
					<div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '10px 18px', borderTop: i < 2 ? 'none' : '1px solid var(--l2-hairline)' }}>
						<span style={{ color: 'var(--l2-fg-3)', fontSize: 12 }}>{k}</span>
						<span style={{ ...mono(11.5, 'var(--l2-fg-1)'), textAlign: 'right', wordBreak: 'break-all' }}>{v}</span>
					</div>
				))}
			</div>
		</section>
	);
}

// ── minimal, dependency-free markdown ────────────────────────────────────────
// Renders the subset wiki bodies use: headings, fenced code, inline code, bold,
// lists, and paragraphs. Deliberately lean (anti-bloat) — no markdown library.
function Markdown({ body }: { body: string }) {
	const blocks = useMemo(() => parseMarkdown(body), [body]);
	if (blocks.length === 0) {
		return <p style={{ color: 'var(--l2-fg-3)', fontSize: 14 }}>This page has no content yet.</p>;
	}
	return <div style={{ color: 'var(--l2-fg-2)', fontSize: 14.5, lineHeight: 1.7 }}>{blocks}</div>;
}

type Block = React.ReactElement;

function parseMarkdown(src: string): Block[] {
	const lines = src.replace(/\r\n/g, '\n').split('\n');
	const out: Block[] = [];
	let i = 0;
	let key = 0;
	while (i < lines.length) {
		const line = lines[i];
		// fenced code
		if (line.trim().startsWith('```')) {
			const buf: string[] = [];
			i++;
			while (i < lines.length && !lines[i].trim().startsWith('```')) {
				buf.push(lines[i]);
				i++;
			}
			i++; // closing fence
			out.push(
				<pre key={key++} style={{ margin: '0 0 16px', padding: '14px 16px', background: 'rgba(9,11,16,0.7)', border: '1px solid var(--l2-hairline)', borderRadius: 2, fontFamily: 'var(--l2-font-mono)', fontSize: 12.5, lineHeight: 1.6, color: 'var(--l2-fg-2)', overflowX: 'auto' }}>
					{buf.join('\n')}
				</pre>
			);
			continue;
		}
		// headings
		const h = /^(#{1,4})\s+(.*)$/.exec(line);
		if (h) {
			const level = h[1].length;
			const size = [22, 19, 16, 14][level - 1];
			out.push(
				<div key={key++} style={{ fontFamily: 'var(--l2-font-serif)', fontWeight: 600, fontSize: size, color: 'var(--l2-fg-1)', margin: '22px 0 10px', lineHeight: 1.2 }}>
					{inline(h[2])}
				</div>
			);
			i++;
			continue;
		}
		// list block
		if (/^\s*[-*]\s+/.test(line)) {
			const items: string[] = [];
			while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
				items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
				i++;
			}
			out.push(
				<ul key={key++} style={{ margin: '0 0 16px', paddingLeft: 20 }}>
					{items.map((it, j) => (
						<li key={j} style={{ marginBottom: 5 }}>{inline(it)}</li>
					))}
				</ul>
			);
			continue;
		}
		// blank line
		if (line.trim() === '') {
			i++;
			continue;
		}
		// paragraph (gather until blank)
		const para: string[] = [];
		while (i < lines.length && lines[i].trim() !== '' && !/^(#{1,4})\s+/.test(lines[i]) && !lines[i].trim().startsWith('```') && !/^\s*[-*]\s+/.test(lines[i])) {
			para.push(lines[i]);
			i++;
		}
		out.push(
			<p key={key++} style={{ margin: '0 0 16px' }}>{inline(para.join(' '))}</p>
		);
	}
	return out;
}

// Inline: **bold** and `code`. Returns React nodes.
function inline(text: string): React.ReactNode[] {
	const parts: React.ReactNode[] = [];
	const re = /(\*\*([^*]+)\*\*|`([^`]+)`)/g;
	let last = 0;
	let m: RegExpExecArray | null;
	let k = 0;
	while ((m = re.exec(text)) !== null) {
		if (m.index > last) parts.push(text.slice(last, m.index));
		if (m[2] !== undefined) {
			parts.push(<strong key={k++} style={{ color: 'var(--l2-fg-1)', fontWeight: 600 }}>{m[2]}</strong>);
		} else if (m[3] !== undefined) {
			parts.push(
				<code key={k++} style={{ fontFamily: 'var(--l2-font-mono)', fontSize: '0.88em', color: 'var(--atlas-celestial)', background: 'rgba(79,139,255,0.08)', padding: '1px 5px', borderRadius: 2 }}>
					{m[3]}
				</code>
			);
		}
		last = m.index + m[0].length;
	}
	if (last < text.length) parts.push(text.slice(last));
	return parts;
}

// ── states ──────────────────────────────────────────────────────────────────
function ViewerEmpty() {
	return (
		<div style={glassPanel({ padding: '56px 32px', textAlign: 'center' })}>
			<img src={sealMark} alt="" aria-hidden="true" style={{ width: 110, opacity: 0.82, marginBottom: 16 }} />
			<div style={{ fontFamily: 'var(--l2-font-serif)', fontSize: 22, color: 'var(--l2-fg-1)', marginBottom: 6 }}>
				Select a page, or search the codex
			</div>
			<div style={{ color: 'var(--l2-fg-3)', fontSize: 13.5, maxWidth: 420, margin: '0 auto', lineHeight: 1.6 }}>
				The codex is ATLAS's memory — every page carries provenance: who wrote it, from which run, at what sensitivity.
			</div>
		</div>
	);
}

function ViewerSkeleton() {
	return (
		<div style={glassPanel({ padding: '28px 32px' })}>
			<div style={{ ...sk('30%'), marginBottom: 16 }} />
			<div style={{ ...sk('70%', false, 22), marginBottom: 20 }} />
			{Array.from({ length: 6 }).map((_, i) => (
				<div key={i} style={{ ...sk(`${70 + ((i * 7) % 25)}%`), marginBottom: 12 }} />
			))}
		</div>
	);
}

function ViewerError({ slug }: { slug: string | null }) {
	return (
		<div style={glassPanel({ padding: '32px' })}>
			<div style={{ color: 'var(--l2-fg-1)', fontSize: 15, marginBottom: 6 }}>Could not load this page</div>
			<div style={mono(12, 'var(--l2-fg-3)')}>{slug ? `FAILED TO FETCH ${slug}` : 'GATEWAY UNAVAILABLE'}</div>
		</div>
	);
}

function ListSkeleton() {
	return (
		<div>
			{Array.from({ length: 7 }).map((_, i) => (
				<div key={i} style={{ padding: '13px 16px', borderTop: i === 0 ? 'none' : '1px solid var(--l2-hairline)' }}>
					<div style={{ ...sk(`${50 + ((i * 11) % 35)}%`), marginBottom: 7 }} />
					<div style={sk('40%')} />
				</div>
			))}
		</div>
	);
}

function Offline() {
	return (
		<div style={{ padding: '24px 16px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
			<span style={{ width: 7, height: 7, marginTop: 4, borderRadius: '50%', background: 'var(--l2-error)', boxShadow: '0 0 9px rgba(255,0,85,0.55)', flex: 'none' }} />
			<div>
				<div style={{ color: 'var(--l2-fg-1)', fontSize: 14, marginBottom: 4 }}>Gateway unavailable</div>
				<div style={mono(11, 'var(--l2-fg-3)')}>NO RESPONSE FROM 127.0.0.1:8484</div>
			</div>
		</div>
	);
}

const sk = (w: number | string, right = false, h = 12): React.CSSProperties => ({
	height: h,
	width: w,
	justifySelf: right ? 'end' : 'start',
	borderRadius: 2,
	background: 'var(--l2-fg-ghost)',
	animation: 'atlas-pulse-soft 1.5s var(--l2-ease) infinite'
});

function mono(size: number, color?: string): React.CSSProperties {
	return { fontFamily: 'var(--l2-font-mono)', fontSize: size, ...(color ? { color } : {}) };
}
