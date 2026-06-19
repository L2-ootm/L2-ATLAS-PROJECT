import { useMemo, useState } from 'react';
import { Check, ChevronDown, Folder, Slash } from 'lucide-react';
import type { Project } from '../lib/api';

interface ProjectSelectorProps {
	projects: Project[];
	value: string;
	onChange: (id: string) => void;
	disabled?: boolean;
}

export default function ProjectSelector({ projects, value, onChange, disabled }: ProjectSelectorProps) {
	const [open, setOpen] = useState(false);
	const selected = useMemo(() => projects.find((p) => p.id === value) ?? null, [projects, value]);
	const activeName = selected?.name ?? 'No project';
	const activePath = selected?.root_path ?? 'Default working directory';

	function pick(id: string) {
		onChange(id);
		setOpen(false);
	}

	return (
		<div
			onKeyDown={(e) => {
				if (e.key === 'Escape') setOpen(false);
			}}
			style={{ position: 'relative' }}
		>
			<button
				type="button"
				disabled={disabled}
				aria-haspopup="listbox"
				aria-expanded={open}
				onClick={() => !disabled && setOpen((v) => !v)}
				style={{
					width: '100%',
					minHeight: 48,
					display: 'grid',
					gridTemplateColumns: '22px 1fr 18px',
					alignItems: 'center',
					gap: 10,
					padding: '8px 12px',
					borderRadius: 2,
					border: `1px solid ${open ? 'rgba(161,123,255,0.72)' : 'var(--l2-hairline)'}`,
					background: open
						? 'linear-gradient(180deg, rgba(20,23,33,0.96), rgba(10,12,18,0.98))'
						: 'rgba(9,11,16,0.76)',
					color: 'var(--l2-fg-1)',
					boxShadow: open ? '0 0 0 1px rgba(161,123,255,0.14), 0 0 28px rgba(161,123,255,0.12)' : 'none',
					cursor: disabled ? 'default' : 'pointer',
					textAlign: 'left',
					transition: 'border-color 150ms var(--l2-ease), box-shadow 150ms var(--l2-ease), background 150ms var(--l2-ease)'
				}}
			>
				<span style={{ color: selected ? 'var(--atlas-cyan)' : 'var(--l2-fg-3)', display: 'flex' }}>
					{selected ? <Folder size={16} strokeWidth={1.5} /> : <Slash size={16} strokeWidth={1.5} />}
				</span>
				<span style={{ minWidth: 0 }}>
					<span
						style={{
							display: 'block',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 12,
							fontWeight: 700,
							color: 'var(--l2-fg-1)',
							whiteSpace: 'nowrap',
							overflow: 'hidden',
							textOverflow: 'ellipsis'
						}}
					>
						{activeName}
					</span>
					<span
						style={{
							display: 'block',
							marginTop: 3,
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10.5,
							color: 'var(--l2-fg-3)',
							whiteSpace: 'nowrap',
							overflow: 'hidden',
							textOverflow: 'ellipsis'
						}}
					>
						{activePath}
					</span>
				</span>
				<ChevronDown
					size={16}
					strokeWidth={1.5}
					style={{
						color: open ? 'var(--atlas-violet)' : 'var(--l2-fg-3)',
						transform: open ? 'rotate(180deg)' : 'none',
						transition: 'transform 150ms var(--l2-ease), color 150ms var(--l2-ease)'
					}}
				/>
			</button>

			{open && (
				<div
					role="listbox"
					aria-label="Project"
					style={{
						marginTop: 7,
						borderRadius: 2,
						border: '1px solid rgba(161,123,255,0.34)',
						background: 'linear-gradient(180deg, rgba(15,18,27,0.98), rgba(7,8,12,0.98))',
						boxShadow: '0 20px 60px rgba(0,0,0,0.55), inset 0 1px 0 rgba(237,234,224,0.07)',
						overflow: 'hidden',
						animation: 'atlas-selector-open 180ms var(--l2-ease)',
						position: 'relative',
						zIndex: 30
					}}
				>
					<ProjectOption
						active={value === ''}
						name="No project"
						path="Default working directory"
						onPick={() => pick('')}
						empty
					/>
					{projects.map((project) => (
						<ProjectOption
							key={project.id}
							active={project.id === value}
							name={project.name}
							path={project.root_path}
							onPick={() => pick(project.id)}
						/>
					))}
				</div>
			)}
		</div>
	);
}

function ProjectOption({
	active,
	name,
	path,
	onPick,
	empty
}: {
	active: boolean;
	name: string;
	path: string;
	onPick: () => void;
	empty?: boolean;
}) {
	return (
		<button
			type="button"
			role="option"
			aria-selected={active}
			onClick={onPick}
			data-topo={empty ? 'atlas' : 'good'}
			style={{
				width: '100%',
				display: 'grid',
				gridTemplateColumns: '18px 1fr 18px',
				alignItems: 'center',
				gap: 10,
				padding: '10px 12px',
				border: 'none',
				borderTop: '1px solid rgba(237,234,224,0.045)',
				background: active ? 'rgba(79,139,255,0.10)' : 'transparent',
				color: 'var(--l2-fg-1)',
				cursor: 'pointer',
				textAlign: 'left'
			}}
			onMouseEnter={(e) => (e.currentTarget.style.background = active ? 'rgba(79,139,255,0.14)' : 'rgba(237,234,224,0.045)')}
			onMouseLeave={(e) => (e.currentTarget.style.background = active ? 'rgba(79,139,255,0.10)' : 'transparent')}
		>
			<span style={{ display: 'flex', color: empty ? 'var(--l2-fg-3)' : 'var(--atlas-cyan)' }}>
				{empty ? <Slash size={14} strokeWidth={1.5} /> : <Folder size={14} strokeWidth={1.5} />}
			</span>
			<span style={{ minWidth: 0 }}>
				<span style={{ display: 'block', fontFamily: 'var(--l2-font-mono)', fontSize: 12, fontWeight: 700 }}>
					{name}
				</span>
				<span
					style={{
						display: 'block',
						marginTop: 3,
						fontFamily: 'var(--l2-font-mono)',
						fontSize: 10.5,
						color: 'var(--l2-fg-3)',
						whiteSpace: 'nowrap',
						overflow: 'hidden',
						textOverflow: 'ellipsis'
					}}
				>
					{path}
				</span>
			</span>
			<Check size={15} strokeWidth={1.7} style={{ color: active ? 'var(--atlas-celestial)' : 'transparent' }} />
		</button>
	);
}
