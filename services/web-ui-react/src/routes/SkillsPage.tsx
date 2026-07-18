import { useCallback, useEffect, useState } from 'react';
import { Search, Package, Layers, Download, ChevronDown } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel, HudLabel } from '../components/hud';

interface SkillInfo {
	id: string;
	name: string;
	description: string;
	version: string;
	author: string;
	license: string;
	category: string;
	tags: string[];
	provenance: {
		tier: 'original' | 'framework' | 'third-party';
		source: 'bundled' | 'hub' | 'user' | 'agent' | 'plugin';
	};
	loading_tier: 'full' | 'name-only' | 'deactivated';
	platforms: string[];
	enabled: boolean;
	pinned: boolean;
	state: 'active' | 'stale' | 'archived';
	usage: {
		use_count: number;
		view_count: number;
		last_used_at: string | null;
	};
	path: string;
}

type Tab = 'installed' | 'store' | 'bundles';

const TABS: { key: Tab; label: string; icon: typeof Package }[] = [
	{ key: 'installed', label: 'INSTALLED', icon: Package },
	{ key: 'store', label: 'STORE', icon: Download },
	{ key: 'bundles', label: 'BUNDLES', icon: Layers }
];

const TIER_LABELS: Record<string, { label: string; color: string }> = {
	full: { label: 'FULL', color: 'var(--atlas-emerald)' },
	'name-only': { label: 'NAME ONLY', color: 'var(--atlas-celestial)' },
	deactivated: { label: 'OFF', color: 'var(--l2-fg-3)' }
};

const PROVENANCE_LABELS: Record<string, { label: string; color: string }> = {
	original: { label: 'ATLAS', color: 'var(--atlas-bronze)' },
	framework: { label: 'HERMES', color: 'var(--atlas-celestial)' },
	'third-party': { label: '3RD PARTY', color: 'var(--l2-fg-3)' }
};

export default function SkillsPage() {
	const [tab, setTab] = useState<Tab>('installed');
	const [skills, setSkills] = useState<SkillInfo[]>([]);
	const [loading, setLoading] = useState(true);
	const [search, setSearch] = useState('');
	const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		setLoading(true);
		try {
			const res = await fetch('http://127.0.0.1:8484/api/skills');
			if (res.ok) {
				const data = await res.json();
				setSkills(data.skills || []);
			}
		} catch {
			// Gateway offline
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const categories = Array.from(new Set(skills.map((s) => s.category))).sort();

	const filtered = skills.filter((s) => {
		if (search) {
			const q = search.toLowerCase();
			if (!s.name.toLowerCase().includes(q) && !s.description.toLowerCase().includes(q) && !s.tags.some((t) => t.includes(q))) {
				return false;
			}
		}
		if (categoryFilter && s.category !== categoryFilter) return false;
		return true;
	});

	return (
		<Page eyebrow="SYSTEM" title="Skills">
			<div style={{ display: 'flex', gap: 16, alignItems: 'start' }}>
				{/* Sidebar */}
				<div style={{ width: 220, flexShrink: 0 }}>
					<GlassPanel style={{ padding: 0, overflow: 'hidden' }}>
						<div style={{ padding: '13px 16px', borderBottom: '1px solid var(--l2-hairline)' }}>
							<HudLabel>CATEGORIES</HudLabel>
						</div>
						<div style={{ padding: 8 }}>
							<button
								type="button"
								onClick={() => setCategoryFilter(null)}
								style={{
									display: 'block',
									width: '100%',
									textAlign: 'left',
									padding: '6px 10px',
									borderRadius: 2,
									border: 'none',
									background: categoryFilter === null ? 'rgba(79,139,255,0.1)' : 'transparent',
									color: categoryFilter === null ? 'var(--atlas-celestial)' : 'var(--l2-fg-2)',
									fontSize: 12.5,
									cursor: 'pointer'
								}}
							>
								All ({skills.length})
							</button>
							{categories.map((cat) => {
								const count = skills.filter((s) => s.category === cat).length;
								return (
									<button
										key={cat}
										type="button"
										onClick={() => setCategoryFilter(cat)}
										style={{
											display: 'block',
											width: '100%',
											textAlign: 'left',
											padding: '6px 10px',
											borderRadius: 2,
											border: 'none',
											background: categoryFilter === cat ? 'rgba(79,139,255,0.1)' : 'transparent',
											color: categoryFilter === cat ? 'var(--atlas-celestial)' : 'var(--l2-fg-2)',
											fontSize: 12.5,
											cursor: 'pointer',
											textTransform: 'capitalize'
										}}
									>
										{cat} ({count})
									</button>
								);
							})}
						</div>
					</GlassPanel>
				</div>

				{/* Main content */}
				<div style={{ flex: 1, minWidth: 0 }}>
					{/* Tabs + Search */}
					<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
						<div style={{ display: 'flex', gap: 4 }}>
							{TABS.map((t) => (
								<button
									key={t.key}
									type="button"
									onClick={() => setTab(t.key)}
									style={{
										display: 'flex',
										alignItems: 'center',
										gap: 6,
										padding: '7px 14px',
										borderRadius: 2,
										border: `1px solid ${tab === t.key ? 'rgba(79,139,255,0.4)' : 'var(--l2-hairline)'}`,
										background: tab === t.key ? 'rgba(79,139,255,0.1)' : 'transparent',
										color: tab === t.key ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
										fontFamily: 'var(--l2-font-mono)',
										fontSize: 10,
										letterSpacing: '0.14em',
										cursor: 'pointer'
									}}
								>
									<t.icon size={13} />
									{t.label}
								</button>
							))}
						</div>
						<div style={{ position: 'relative' }}>
							<Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--l2-fg-3)' }} />
							<input
								value={search}
								onChange={(e) => setSearch(e.target.value)}
								placeholder="Search skills…"
								style={{
									padding: '7px 10px 7px 30px',
									borderRadius: 2,
									border: '1px solid var(--l2-hairline)',
									background: 'rgba(9,11,16,0.72)',
									color: 'var(--l2-fg-1)',
									fontSize: 12.5,
									width: 240
								}}
							/>
						</div>
					</div>

					{/* Skills grid */}
					{loading ? (
						<GlassPanel style={{ padding: 48, display: 'grid', placeItems: 'center' }}>
							<HudLabel>LOADING…</HudLabel>
						</GlassPanel>
					) : filtered.length === 0 ? (
						<GlassPanel style={{ padding: 48, display: 'grid', placeItems: 'center' }}>
							<div style={{ color: 'var(--l2-fg-3)', fontSize: 13 }}>
								{search ? 'No skills match your search.' : 'No skills found.'}
							</div>
						</GlassPanel>
					) : (
						<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
							{filtered.map((skill) => (
								<SkillCard key={skill.id} skill={skill} onUpdate={refresh} />
							))}
						</div>
					)}
				</div>
			</div>
		</Page>
	);
}

function SkillCard({ skill, onUpdate }: { skill: SkillInfo; onUpdate: () => void }) {
	const [tierOpen, setTierOpen] = useState(false);
	const tier = TIER_LABELS[skill.loading_tier] || TIER_LABELS.full;
	const provenance = PROVENANCE_LABELS[skill.provenance?.tier] || PROVENANCE_LABELS['third-party'];

	async function setTier(newTier: string) {
		try {
			await fetch('http://127.0.0.1:8484/api/skills/tier', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ id: skill.id, tier: newTier })
			});
			setTierOpen(false);
			onUpdate();
		} catch {
			// ignore
		}
	}

	return (
		<GlassPanel style={{ padding: 0, overflow: 'hidden' }}>
			<div style={{ padding: '12px 14px' }}>
				<div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
					<div style={{ flex: 1, minWidth: 0 }}>
						<div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
							<span style={{ fontSize: 14, fontWeight: 600, color: 'var(--l2-fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
								{skill.name}
							</span>
							<span style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 8.5,
								letterSpacing: '0.14em',
								color: provenance.color,
								padding: '2px 5px',
								borderRadius: 2,
								border: `1px solid ${provenance.color}33`
							}}>
								{provenance.label}
							</span>
						</div>
						<div style={{ fontSize: 12, color: 'var(--l2-fg-3)', lineHeight: 1.45, marginBottom: 8 }}>
							{skill.description}
						</div>
					</div>
					<div style={{ position: 'relative', flexShrink: 0 }}>
						<button
							type="button"
							onClick={() => setTierOpen(!tierOpen)}
							style={{
								display: 'flex',
								alignItems: 'center',
								gap: 4,
								padding: '4px 8px',
								borderRadius: 2,
								border: `1px solid ${tier.color}44`,
								background: `${tier.color}11`,
								color: tier.color,
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 9,
								letterSpacing: '0.14em',
								cursor: 'pointer'
							}}
						>
							{tier.label}
							<ChevronDown size={10} />
						</button>
						{tierOpen && (
							<>
								<div onClick={() => setTierOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
								<div style={{
									position: 'absolute',
									top: 24,
									right: 0,
									zIndex: 41,
									width: 120,
									borderRadius: 2,
									border: '1px solid var(--l2-hairline)',
									background: 'linear-gradient(160deg, rgba(20,24,33,0.98), rgba(10,12,18,0.98))',
									boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
									overflow: 'hidden'
								}}>
									{Object.entries(TIER_LABELS).map(([key, val]) => (
										<button
											key={key}
											type="button"
											onClick={() => setTier(key)}
											style={{
												display: 'block',
												width: '100%',
												textAlign: 'left',
												padding: '7px 10px',
												border: 'none',
												borderBottom: '1px solid var(--l2-hairline)',
												background: skill.loading_tier === key ? 'rgba(79,139,255,0.08)' : 'transparent',
												color: val.color,
												fontFamily: 'var(--l2-font-mono)',
												fontSize: 9.5,
												letterSpacing: '0.12em',
												cursor: 'pointer'
											}}
										>
											{val.label}
										</button>
									))}
								</div>
							</>
						)}
					</div>
				</div>
				<div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: 'var(--l2-font-mono)', fontSize: 10, color: 'var(--l2-fg-3)' }}>
					<span>v{skill.version}</span>
					<span>{skill.category}</span>
					{skill.usage?.use_count > 0 && <span>{skill.usage.use_count} uses</span>}
					<span style={{ marginLeft: 'auto' }}>{skill.author}</span>
				</div>
				{skill.tags?.length > 0 && (
					<div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 8 }}>
						{skill.tags.slice(0, 5).map((tag) => (
							<span key={tag} style={{
								padding: '2px 6px',
								borderRadius: 2,
								border: '1px solid rgba(237,234,224,0.08)',
								fontSize: 10,
								color: 'var(--l2-fg-3)'
							}}>
								{tag}
							</span>
						))}
					</div>
				)}
			</div>
		</GlassPanel>
	);
}
