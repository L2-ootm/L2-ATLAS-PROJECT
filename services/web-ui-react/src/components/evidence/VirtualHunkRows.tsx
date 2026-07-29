import { useMemo, useState } from 'react';

export interface EvidenceDiffRow {
	id: string;
	kind: 'add' | 'remove' | 'context' | 'header';
	text: string;
	oldLine: number | null;
	newLine: number | null;
}

const ROW_HEIGHT = 22;
const OVERSCAN = 24;
const MAX_RENDERED_ROWS = 250;

export function VirtualHunkRows({
	rows,
	view,
	search
}: {
	rows: EvidenceDiffRow[];
	view: 'unified' | 'side-by-side';
	search: string;
}) {
	const [scrollTop, setScrollTop] = useState(0);
	const viewportHeight = 440;
	const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT);
	const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
	const end = Math.min(
		rows.length,
		start + Math.min(MAX_RENDERED_ROWS, visibleCount + OVERSCAN * 2)
	);
	const windowed = useMemo(() => rows.slice(start, end), [end, rows, start]);
	const needle = search.trim().toLowerCase();

	return (
		<div
			data-testid="evidence-virtual-rows"
			onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
			style={{ position: 'relative', height: viewportHeight, overflow: 'auto' }}
		>
			<div style={{ position: 'relative', height: rows.length * ROW_HEIGHT }}>
				{windowed.map((row, index) => {
					const absoluteIndex = start + index;
					const matched = needle !== '' && row.text.toLowerCase().includes(needle);
					const tone =
						row.kind === 'add'
							? 'rgba(70,240,160,0.10)'
							: row.kind === 'remove'
								? 'rgba(255,77,125,0.10)'
								: row.kind === 'header'
									? 'rgba(79,139,255,0.10)'
									: 'transparent';
					return (
						<div
							key={row.id}
							data-evidence-row
							style={{
								position: 'absolute',
								top: absoluteIndex * ROW_HEIGHT,
								left: 0,
								right: 0,
								height: ROW_HEIGHT,
								display: 'grid',
								gridTemplateColumns:
									view === 'side-by-side'
										? '52px minmax(0, 1fr) 52px minmax(0, 1fr)'
										: '52px 52px minmax(0, 1fr)',
								alignItems: 'center',
								background: matched ? 'rgba(255,214,0,0.15)' : tone,
								borderBottom: '1px solid rgba(237,234,224,0.035)',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 11.5,
								whiteSpace: 'pre'
							}}
						>
							{view === 'side-by-side' ? (
								<>
									<LineNumber value={row.oldLine} />
									<span style={{ overflow: 'hidden', color: row.kind === 'remove' ? '#ffb3c6' : 'var(--l2-fg-3)' }}>
										{row.kind === 'add' ? '' : row.text}
									</span>
									<LineNumber value={row.newLine} />
									<span style={{ overflow: 'hidden', color: row.kind === 'add' ? '#9bf3c9' : 'var(--l2-fg-3)' }}>
										{row.kind === 'remove' ? '' : row.text}
									</span>
								</>
							) : (
								<>
									<LineNumber value={row.oldLine} />
									<LineNumber value={row.newLine} />
									<span style={{ overflow: 'hidden', color: row.kind === 'add' ? '#9bf3c9' : row.kind === 'remove' ? '#ffb3c6' : 'var(--l2-fg-2)' }}>
										{row.text}
									</span>
								</>
							)}
						</div>
					);
				})}
			</div>
		</div>
	);
}

function LineNumber({ value }: { value: number | null }) {
	return (
		<span
			aria-hidden="true"
			style={{ textAlign: 'right', paddingRight: 9, color: 'var(--l2-fg-3)', opacity: 0.7 }}
		>
			{value ?? ''}
		</span>
	);
}

