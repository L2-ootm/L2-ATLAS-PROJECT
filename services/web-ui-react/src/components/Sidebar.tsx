import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronLeft, ChevronRight, GitBranch, Wallet, Boxes, type LucideIcon } from 'lucide-react';
import { navSections, type CockpitModule, type NavSection } from '../lib/modules';
import { listModules, getVcsContext, type VcsContext } from '../lib/api';
import { useGatewayHealth } from '../lib/useGatewayHealth';

// Active optional modules (Decision 3b) render as a dynamic nav section. Map known
// module ids to an icon; unknown modules fall back to a generic one.
const MODULE_ICON: Record<string, LucideIcon> = { cashflow: Wallet };
import { SIDEBAR_WIDTH_COLLAPSED, SIDEBAR_WIDTH_EXPANDED } from '../lib/ui-state';
import AtlasMark from '../brand/AtlasMark';
import { Wordmark } from '../brand/Wordmark';

interface SidebarProps {
	expanded: boolean;
	onToggle: () => void;
}

export default function Sidebar({ expanded, onToggle }: SidebarProps) {
	const width = expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED;
	const { pathname } = useLocation();

	// ── Gateway health — shared heartbeat (live, no manual refresh) ──────────
	const { online: gatewayOnline, epoch } = useGatewayHealth();
	// ── Active optional modules (drive the dynamic nav section) ──────────────
	const [activeModuleNav, setActiveModuleNav] = useState<CockpitModule[]>([]);

	// Refetch the module nav on (re)connect (epoch) and on a slow interval.
	useEffect(() => {
		let alive = true;
		async function loadModules() {
			try {
				const { modules } = await listModules();
				if (!alive) return;
				setActiveModuleNav(
					modules
						.filter((m) => m.status === 'active' && !m.missing)
						.map((m) => ({
							id: m.id,
							label: m.name.toUpperCase(),
							// Manifest modules with pages render in the schema host;
							// legacy built-ins (cashflow) keep their dedicated routes.
							route: m.manifest?.capabilities?.pages?.length ? `/m/${m.id}` : `/${m.id}`,
							icon: MODULE_ICON[m.id] ?? Boxes,
							status: 'active' as const,
							ariaLabel: m.name
						}))
				);
			} catch {
				if (alive) setActiveModuleNav([]);
			}
		}
		void loadModules();
		const id = setInterval(() => void loadModules(), 30_000);
		return () => {
			alive = false;
			clearInterval(id);
		};
	}, [epoch]);

	// ── VCS context — git branch of the gateway's repo root ──────────────────
	const [vcs, setVcs] = useState<VcsContext | null>(null);
	useEffect(() => {
		let alive = true;
		async function loadVcs() {
			try {
				const ctx = await getVcsContext();
				if (alive) setVcs(ctx);
			} catch {
				// Pre-/v1/vcs gateway or offline — hide the row rather than error.
				if (alive) setVcs(null);
			}
		}
		void loadVcs();
		const id = setInterval(() => void loadVcs(), 30_000);
		return () => {
			alive = false;
			clearInterval(id);
		};
	}, [epoch]);

	// navSections + a dynamic MODULES section when any optional module is active.
	const sections: NavSection[] =
		activeModuleNav.length > 0
			? [...navSections, { pillar: 'MODULES', items: activeModuleNav }]
			: navSections;

	// Active route: exact match for index/"/", prefix match otherwise.
	const isActive = (route: string, exact?: boolean) =>
		exact || route === '/' ? pathname === route : pathname.startsWith(route);

	const statusColor =
		gatewayOnline === true
			? 'var(--l2-success)'
			: gatewayOnline === false
				? 'var(--l2-error)'
				: 'var(--l2-fg-3)';
	const statusTopo = gatewayOnline === true ? 'good' : gatewayOnline === false ? 'bad' : 'atlas';

	return (
		<nav
			aria-label="Main navigation"
			data-topo="atlas"
			style={{
				position: 'fixed',
				top: 0,
				left: 0,
				bottom: 0,
				width: `${width}px`,
				background: 'linear-gradient(180deg, rgba(10,10,12,0.82), rgba(5,5,7,0.92))',
				backdropFilter: 'blur(14px) saturate(1.3)',
				display: 'flex',
				flexDirection: 'column',
				borderRight: '1px solid var(--l2-glass-border-lo)',
				boxShadow: '1px 0 0 rgba(0,0,0,0.6), 8px 0 32px rgba(0,0,0,0.45)',
				transition: 'width var(--l2-duration-sm) var(--l2-ease)',
				zIndex: 100,
				overflow: 'hidden'
			}}
		>
			{/* ── Brand header — ATLAS-forward ──────────────────────────────────── */}
			<Link
				to="/"
				aria-label="ATLAS home"
				style={{
					display: 'flex',
					alignItems: 'center',
					gap: 12,
					height: 72,
					padding: `0 ${expanded ? '18px' : '0'}`,
					justifyContent: expanded ? 'flex-start' : 'center',
					textDecoration: 'none',
					borderBottom: '1px solid var(--l2-glass-border-lo)',
					flex: 'none'
				}}
			>
				<AtlasMark variant="celestial" tone="color" size={32} />
				{expanded && (
					<div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
						<Wordmark fontSize={19} tracking="0.30em" style={{ alignItems: 'flex-start' }} />
						<span
							style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 8,
								letterSpacing: '0.30em',
								textTransform: 'uppercase',
								color: 'var(--l2-fg-3)',
								whiteSpace: 'nowrap'
							}}
						>
							OPERATOR COCKPIT
						</span>
					</div>
				)}
			</Link>

			{/* ── Collapse toggle ───────────────────────────────────────────────── */}
			<button
				onClick={onToggle}
				aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
				style={{
					display: 'flex',
					alignItems: 'center',
					justifyContent: expanded ? 'flex-end' : 'center',
					width: '100%',
					height: 34,
					padding: expanded ? '0 18px' : '0',
					background: 'none',
					border: 'none',
					borderBottom: '1px solid var(--l2-glass-border-lo)',
					cursor: 'pointer',
					color: 'var(--l2-fg-3)',
					transition: 'color var(--l2-duration-xs) var(--l2-ease)'
				}}
				onMouseEnter={(e) => {
					e.currentTarget.style.color = 'var(--atlas-celestial)';
				}}
				onMouseLeave={(e) => {
					e.currentTarget.style.color = 'var(--l2-fg-3)';
				}}
			>
				{expanded ? (
					<ChevronLeft size={15} strokeWidth={1.5} />
				) : (
					<ChevronRight size={15} strokeWidth={1.5} />
				)}
			</button>

			{/* ── Navigation — pillared (MISSION / AUDIT / STRUCTURE / SYSTEM) ───── */}
			<div role="navigation" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '8px 0' }}>
				{sections.map((section, si) => (
					<div key={section.pillar ?? 'top'} style={{ marginTop: si === 0 ? 2 : expanded ? 14 : 10 }}>
						{section.pillar &&
							(expanded ? (
								<div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 18px 6px' }}>
									<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 8.5, letterSpacing: '0.28em', color: 'var(--atlas-bronze)', opacity: 0.85, whiteSpace: 'nowrap' }}>
										{section.pillar}
									</span>
									<span aria-hidden="true" style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, var(--atlas-bronze-soft), transparent)' }} />
								</div>
							) : (
								<div aria-hidden="true" title={section.pillar} style={{ height: 1, margin: '8px 16px', background: 'var(--atlas-bronze-soft)' }} />
							))}
						<ul role="list" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
							{section.items.map((mod) => {
								const active = isActive(mod.route, mod.exact);
								const planned = mod.status === 'planned';
								const Icon = mod.icon;
								return (
									<li key={mod.id}>
							<Link
								to={mod.route}
								data-topo={active ? 'info' : 'atlas'}
								aria-label={expanded ? undefined : mod.ariaLabel}
								aria-current={active ? 'page' : undefined}
								style={{
									position: 'relative',
									display: 'flex',
									alignItems: 'center',
									gap: expanded ? 14 : 0,
									justifyContent: expanded ? 'flex-start' : 'center',
									height: 46,
									margin: '2px 8px',
									padding: expanded ? '0 12px' : '0',
									borderRadius: 'var(--l2-radius)',
									textDecoration: 'none',
									opacity: planned && !active ? 0.45 : 1,
									background: active ? 'rgba(79,139,255,0.09)' : 'transparent',
									color: active ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
									boxShadow: active ? 'inset 0 0 0 1px rgba(79,139,255,0.20)' : 'none',
									transition:
										'background var(--l2-duration-xs) var(--l2-ease), color var(--l2-duration-xs) var(--l2-ease)'
								}}
								onMouseEnter={(e) => {
									if (!active) {
										e.currentTarget.style.background = 'var(--l2-glass-bg-lo)';
										e.currentTarget.style.color = 'var(--l2-fg-1)';
									}
								}}
								onMouseLeave={(e) => {
									if (!active) {
										e.currentTarget.style.background = 'transparent';
										e.currentTarget.style.color = 'var(--l2-fg-3)';
									}
								}}
							>
								{active && (
									<span
										aria-hidden="true"
										style={{
											position: 'absolute',
											left: -8,
											top: '50%',
											transform: 'translateY(-50%)',
											width: 3,
											height: 22,
											borderRadius: '0 2px 2px 0',
											background: 'var(--atlas-celestial)',
											boxShadow: '0 0 12px var(--atlas-celestial-glow)'
										}}
									/>
								)}
								<Icon size={expanded ? 17 : 20} strokeWidth={1.5} color="currentColor" />
								{expanded && (
									<span
										style={{
											fontFamily: 'var(--l2-font-mono)',
											fontSize: 12,
											fontWeight: 500,
											textTransform: 'uppercase',
											letterSpacing: '0.16em',
											whiteSpace: 'nowrap'
										}}
									>
										{mod.label}
									</span>
								)}
								{expanded && planned && (
									<span
										style={{
											marginLeft: 'auto',
											fontFamily: 'var(--l2-font-mono)',
											fontSize: 8,
											letterSpacing: '0.18em',
											color: 'var(--atlas-bronze)',
											border: '1px solid var(--atlas-bronze-soft)',
											borderRadius: 2,
											padding: '1px 5px'
										}}
									>
										SOON
									</span>
								)}
							</Link>
								</li>
								);
							})}
						</ul>
					</div>
				))}
			</div>

			{/* ── Footer — gateway status + L2 endorsement ──────────────────────── */}
			<div
				data-topo={statusTopo}
				style={{
					padding: expanded ? '14px 18px' : '14px 0',
					borderTop: '1px solid var(--l2-glass-border-lo)',
					display: 'flex',
					flexDirection: 'column',
					gap: 10,
					alignItems: expanded ? 'stretch' : 'center',
					flex: 'none'
				}}
			>
				<div
					style={{
						display: 'flex',
						alignItems: 'center',
						gap: 8,
						justifyContent: expanded ? 'flex-start' : 'center'
					}}
				>
					<span
						aria-hidden="true"
						style={{
							width: 7,
							height: 7,
							borderRadius: '50%',
							background: statusColor,
							boxShadow: `0 0 8px ${statusColor}`,
							flex: 'none',
							transition: 'background 600ms var(--l2-ease), box-shadow 600ms var(--l2-ease)',
							// Gentle heartbeat while online so the live status reads as "alive".
							animation: gatewayOnline === true ? 'atlas-heartbeat 2.4s var(--l2-ease) infinite' : 'none'
						}}
					/>
					{expanded && (
						<span
							style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 10,
								textTransform: 'uppercase',
								letterSpacing: '0.16em',
								color: statusColor
							}}
						>
							{gatewayOnline === true
								? 'GATEWAY · ONLINE'
								: gatewayOnline === false
									? 'GATEWAY · OFFLINE'
									: 'GATEWAY · CHECKING'}
						</span>
					)}
				</div>

				{expanded && vcs?.repo && (
					<div
						title={vcs.detached ? 'Detached HEAD' : 'Current git branch'}
						style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}
					>
						<GitBranch size={11} strokeWidth={1.7} color="var(--atlas-bronze)" aria-hidden="true" style={{ flex: 'none' }} />
						<span
							style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 10,
								letterSpacing: '0.10em',
								color: 'var(--l2-fg-2)',
								overflow: 'hidden',
								textOverflow: 'ellipsis',
								whiteSpace: 'nowrap'
							}}
						>
							{vcs.detached ? `DETACHED · ${vcs.commit ?? '???????'}` : vcs.branch}
						</span>
					</div>
				)}

				{expanded && (
					<div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--l2-fg-3)' }}>
						<svg
							width="11"
							height="11"
							viewBox="0 0 24 24"
							fill="none"
							stroke="var(--l2-fg-2)"
							strokeWidth="3"
							strokeLinecap="square"
							aria-hidden="true"
						>
							<path d="M5 5 V19 H13 M15 5 H19 V11 H15 V19 H19" />
						</svg>
						<span
							style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 9,
								letterSpacing: '0.22em',
								textTransform: 'uppercase'
							}}
						>
							BY L2 SYSTEMS
						</span>
					</div>
				)}
			</div>
		</nav>
	);
}
