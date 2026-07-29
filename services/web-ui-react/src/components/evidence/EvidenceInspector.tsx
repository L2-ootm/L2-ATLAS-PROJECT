import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
	ChevronLeft,
	ChevronRight,
	Download,
	Search,
	X
} from 'lucide-react';
import {
	getFileChangePatch,
	listFileChangeHunks,
	type EvidenceContentPage,
	type EvidenceFileChange,
	type EvidenceHunk
} from '../../lib/api';
import { VirtualHunkRows, type EvidenceDiffRow } from './VirtualHunkRows';

const INITIAL_PATCH_BYTES = 16_384;
const MIN_WIDTH = 560;
const MAX_WIDTH = 1_400;

export interface EvidenceInspectorProvenance {
	actorId: string | null;
	runId: string;
	toolCallId: string | null;
}

function rowsFromPatch(content: string): EvidenceDiffRow[] {
	let oldLine = 0;
	let newLine = 0;
	return content.split('\n').map((text, index) => {
		let kind: EvidenceDiffRow['kind'] = 'context';
		if (text.startsWith('@@')) {
			kind = 'header';
			const match = /@@ -(\d+)(?:,\d+)? \+(\d+)/.exec(text);
			if (match) {
				oldLine = Number(match[1]);
				newLine = Number(match[2]);
			}
		} else if (text.startsWith('+') && !text.startsWith('+++')) {
			kind = 'add';
		} else if (text.startsWith('-') && !text.startsWith('---')) {
			kind = 'remove';
		}
		const row: EvidenceDiffRow = {
			id: `${index}-${text.slice(0, 32)}`,
			kind,
			text,
			oldLine: kind === 'add' || kind === 'header' ? null : oldLine,
			newLine: kind === 'remove' || kind === 'header' ? null : newLine
		};
		if (kind !== 'add' && kind !== 'header') oldLine += 1;
		if (kind !== 'remove' && kind !== 'header') newLine += 1;
		return row;
	});
}

export function EvidenceInspector({
	file,
	ownerToken,
	provenance,
	onClose
}: {
	file: EvidenceFileChange;
	ownerToken: string;
	provenance: EvidenceInspectorProvenance;
	onClose: () => void;
}) {
	const dialogRef = useRef<HTMLDivElement>(null);
	const previousFocus = useRef<HTMLElement | null>(null);
	const requestRef = useRef<AbortController | null>(null);
	const [width, setWidth] = useState(960);
	const [view, setView] = useState<'unified' | 'side-by-side'>('unified');
	const [context, setContext] = useState(3);
	const [ignoreWhitespace, setIgnoreWhitespace] = useState(false);
	const [hunks, setHunks] = useState<EvidenceHunk[]>([]);
	const [nextCursor, setNextCursor] = useState<string | null>(null);
	const [page, setPage] = useState<EvidenceContentPage | null>(null);
	const [search, setSearch] = useState('');
	const [status, setStatus] = useState('Loading evidence');
	const [selectedHunk, setSelectedHunk] = useState(0);

	const load = useCallback(
		async (after?: string, patchOffset = 0, patchLimit = INITIAL_PATCH_BYTES) => {
			requestRef.current?.abort();
			const controller = new AbortController();
			requestRef.current = controller;
			setStatus('Loading evidence');
			try {
				const [hunkPage, patchPage] = await Promise.all([
					listFileChangeHunks(file.id, ownerToken, {
						after,
						limit: 100,
						context,
						ignoreWhitespace,
						signal: controller.signal
					}),
					getFileChangePatch(file.id, ownerToken, {
						offset: patchOffset,
						limit: Math.min(INITIAL_PATCH_BYTES, Math.max(1, patchLimit)),
						signal: controller.signal
					})
				]);
				setHunks((current) => (after ? [...current, ...hunkPage.hunks] : hunkPage.hunks));
				setNextCursor(hunkPage.next_cursor);
				setPage(patchPage);
				setStatus(
					patchPage.availability === 'available'
						? `${hunkPage.hunks.length} hunks loaded`
						: `${patchPage.availability} evidence loaded`
				);
			} catch (reason) {
				if (reason instanceof DOMException && reason.name === 'AbortError') return;
				setStatus('Evidence unavailable');
			}
		},
		[context, file.id, ignoreWhitespace, ownerToken]
	);

	useEffect(() => {
		void load();
		return () => requestRef.current?.abort();
	}, [load]);

	useEffect(() => {
		previousFocus.current = document.activeElement as HTMLElement | null;
		dialogRef.current?.focus();
		return () => previousFocus.current?.focus();
	}, []);

	useEffect(() => {
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				event.preventDefault();
				previousFocus.current?.focus();
				onClose();
				return;
			}
			if (event.key !== 'Tab' || !dialogRef.current) return;
			const focusable = Array.from(
				dialogRef.current.querySelectorAll<HTMLElement>(
					'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
				)
			);
			if (focusable.length === 0) {
				event.preventDefault();
				dialogRef.current.focus();
				return;
			}
			const first = focusable[0];
			const last = focusable.at(-1)!;
			if (event.shiftKey && document.activeElement === first) {
				event.preventDefault();
				last.focus();
			} else if (!event.shiftKey && document.activeElement === last) {
				event.preventDefault();
				first.focus();
			}
		};
		window.addEventListener('keydown', onKeyDown);
		return () => window.removeEventListener('keydown', onKeyDown);
	}, [onClose]);

	const rows = useMemo(() => rowsFromPatch(page?.content ?? ''), [page?.content]);
	const matchCount = useMemo(() => {
		const needle = search.trim().toLowerCase();
		return needle ? rows.filter((row) => row.text.toLowerCase().includes(needle)).length : 0;
	}, [rows, search]);

	const resize = (delta: number) =>
		setWidth((current) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, current + delta)));

	const beginPointerResize = (event: React.PointerEvent<HTMLDivElement>) => {
		const start = event.clientX;
		const initial = width;
		const move = (moveEvent: PointerEvent) => {
			setWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, initial - (moveEvent.clientX - start))));
		};
		const stop = () => {
			window.removeEventListener('pointermove', move);
			window.removeEventListener('pointerup', stop);
		};
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', stop);
	};

	const selectHunk = (index: number) => {
		const bounded = Math.min(hunks.length - 1, Math.max(0, index));
		const hunk = hunks[bounded];
		if (!hunk) return;
		setSelectedHunk(bounded);
		void load(undefined, hunk.patch_start_byte, hunk.patch_bytes);
	};

	const exportLoadedPatch = () => {
		if (!page?.content) return;
		const blob = new Blob([page.content], { type: 'text/x-diff' });
		if (typeof URL.createObjectURL !== 'function') return;
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = `${file.path.split(/[\\/]/).at(-1) ?? 'change'}.loaded.patch`;
		anchor.click();
		URL.revokeObjectURL(url);
	};

	const partial = page && (
		page.availability !== 'available' ||
		page.range.start > 0 ||
		page.range.end < page.range.total_bytes
	);

	return (
		<div
			style={{ position: 'fixed', inset: 0, zIndex: 350, background: 'rgba(5,6,10,0.78)' }}
			onMouseDown={(event) => {
				if (event.currentTarget === event.target) onClose();
			}}
		>
			<div
				ref={dialogRef}
				role="dialog"
				aria-modal="true"
				aria-label={`Evidence inspector — ${file.path}`}
				tabIndex={-1}
				style={{
					position: 'absolute',
					inset: '3vh 0 3vh auto',
					width: `min(${width}px, 96vw)`,
					display: 'flex',
					flexDirection: 'column',
					outline: 'none',
					border: '1px solid var(--l2-hairline)',
					background: 'linear-gradient(160deg, rgba(20,24,33,0.99), rgba(8,10,15,0.99))',
					boxShadow: '-24px 0 80px rgba(0,0,0,0.62)'
				}}
			>
				<div
					role="separator"
					aria-label="Resize evidence inspector"
					aria-orientation="vertical"
					aria-valuemin={MIN_WIDTH}
					aria-valuemax={MAX_WIDTH}
					aria-valuenow={width}
					tabIndex={0}
					onPointerDown={beginPointerResize}
					onKeyDown={(event) => {
						if (event.key === 'ArrowLeft') resize(32);
						if (event.key === 'ArrowRight') resize(-32);
					}}
					style={{ position: 'absolute', inset: '0 auto 0 -5px', width: 10, cursor: 'ew-resize' }}
				/>
				<header style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderBottom: '1px solid var(--l2-hairline)' }}>
					<span style={{ color: 'var(--atlas-celestial)', fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.14em' }}>
						{file.operation.toUpperCase()}
					</span>
					<strong style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.path}</strong>
					<span style={{ marginLeft: 'auto', color: 'var(--l2-good)' }}>+{file.additions}</span>
					<span style={{ color: 'var(--l2-error)' }}>−{file.deletions}</span>
					<button type="button" aria-label="Close evidence inspector" onClick={onClose}><X size={15} /></button>
				</header>

				<div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 14px', borderBottom: '1px solid var(--l2-hairline)', flexWrap: 'wrap' }}>
					<button type="button" onClick={() => selectHunk(selectedHunk - 1)} disabled={selectedHunk <= 0} aria-label="Previous hunk"><ChevronLeft size={14} /></button>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10 }}>
						HUNK {hunks.length ? selectedHunk + 1 : 0}/{hunks.length}
					</span>
					<button type="button" onClick={() => selectHunk(selectedHunk + 1)} disabled={selectedHunk >= hunks.length - 1} aria-label="Next hunk"><ChevronRight size={14} /></button>
					{nextCursor && (
						<button type="button" onClick={() => void load(nextCursor)}>LOAD NEXT PAGE</button>
					)}
					<button type="button" aria-pressed={view === 'unified'} onClick={() => setView('unified')}>UNIFIED</button>
					<button type="button" aria-pressed={view === 'side-by-side'} onClick={() => setView('side-by-side')}>SIDE BY SIDE</button>
					<label>
						CONTEXT
						<select value={context} onChange={(event) => setContext(Number(event.target.value))}>
							<option value={0}>0</option>
							<option value={3}>3</option>
							<option value={10}>10</option>
						</select>
					</label>
					<label>
						<input type="checkbox" checked={ignoreWhitespace} onChange={(event) => setIgnoreWhitespace(event.target.checked)} />
						IGNORE WHITESPACE
					</label>
					<label style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
						<Search size={13} />
						<input aria-label="Search loaded evidence" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search loaded page" />
					</label>
					{search && <span>{matchCount} MATCHES</span>}
					<button type="button" onClick={exportLoadedPatch} disabled={!page?.content}><Download size={13} /> EXPORT LOADED PATCH</button>
				</div>

				<div role="status" aria-live="polite" style={{ padding: '6px 14px', fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: partial ? 'var(--l2-warning, #f2b65a)' : 'var(--l2-fg-3)' }}>
					{partial ? `PARTIAL EVIDENCE · ${status}` : status}
				</div>

				<div style={{ flex: 1, minHeight: 0, borderTop: '1px solid rgba(237,234,224,0.05)' }}>
					{page?.content ? (
						<VirtualHunkRows rows={rows} view={view} search={search} />
					) : (
						<div style={{ padding: 24, color: 'var(--l2-fg-3)' }}>{status}</div>
					)}
				</div>

				<footer style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12, padding: '8px 14px', borderTop: '1px solid var(--l2-hairline)', fontFamily: 'var(--l2-font-mono)', fontSize: 10 }}>
					<span>RUN {provenance.runId}</span>
					<span>ACTOR {provenance.actorId ?? 'operator'}</span>
					<span>CALL {provenance.toolCallId ?? 'unattributed'}</span>
				</footer>
			</div>
		</div>
	);
}

