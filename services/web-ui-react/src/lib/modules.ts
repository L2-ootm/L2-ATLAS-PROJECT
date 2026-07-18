import type { LucideIcon } from 'lucide-react';
import {
	Compass,
	Crosshair,
	Map,
	Activity,
	MessageSquare,
	MessagesSquare,
	ScrollText,
	BookOpen,
	Boxes,
	Cable,
	FolderGit2,
	Share2,
	SlidersHorizontal,
	Hash,
	Package,
	Users
} from 'lucide-react';

export type ModuleStatus = 'active' | 'beta' | 'planned';

export interface CockpitModule {
	id: string;
	label: string;
	route: string;
	icon: LucideIcon;
	status: ModuleStatus;
	ariaLabel: string;
	/** exact route match for active state (e.g. the index route) */
	exact?: boolean;
}

export interface NavSection {
	/** pillar header; null = ungrouped top items */
	pillar: string | null;
	items: CockpitModule[];
}

// Pillared navigation — the thesis (MISSION / AUDIT / STRUCTURE) is the IA.
// Single source of truth for the sidebar; new surfaces register here, no shell rewiring.
export const navSections: NavSection[] = [
	{
		pillar: null,
		items: [
			{ id: 'observatory', label: 'OVERVIEW', route: '/', icon: Compass, status: 'active', ariaLabel: 'Observatory', exact: true }
		]
	},
	{
		pillar: 'MISSION',
		items: [
			{ id: 'command', label: 'COMMAND', route: '/command', icon: Crosshair, status: 'active', ariaLabel: 'Command Center' },
			{ id: 'missions', label: 'MISSIONS', route: '/missions', icon: Map, status: 'active', ariaLabel: 'Missions' },
			{ id: 'runs', label: 'RUNS', route: '/runs', icon: Activity, status: 'active', ariaLabel: 'Runs' },
			{ id: 'chat', label: 'CHAT', route: '/chat', icon: MessagesSquare, status: 'active', ariaLabel: 'Chat' },
			{ id: 'console', label: 'CONSOLE', route: '/console', icon: MessageSquare, status: 'active', ariaLabel: 'Console' },
			{ id: 'teams', label: 'TEAMS', route: '/teams', icon: Users, status: 'beta', ariaLabel: 'Agent Teams' }
		]
	},
	{
		pillar: 'AUDIT',
		items: [
			{ id: 'audit', label: 'LEDGER', route: '/audit', icon: ScrollText, status: 'beta', ariaLabel: 'Audit Ledger' }
		]
	},
	{
		pillar: 'STRUCTURE',
		items: [
			{ id: 'projects', label: 'PROJECTS', route: '/projects', icon: FolderGit2, status: 'active', ariaLabel: 'Projects' },
			{ id: 'graph', label: 'GRAPHIFY', route: '/graph', icon: Share2, status: 'active', ariaLabel: 'Knowledge Graph' },
			{ id: 'wiki', label: 'CODEX', route: '/wiki', icon: BookOpen, status: 'active', ariaLabel: 'Codex' },
			{ id: 'models', label: 'MODELS', route: '/models', icon: Boxes, status: 'active', ariaLabel: 'Model Registry' },
			{ id: 'skills', label: 'SKILLS', route: '/skills', icon: Package, status: 'beta', ariaLabel: 'Skills' },
			{ id: 'discord', label: 'DISCORD', route: '/discord', icon: Hash, status: 'active', ariaLabel: 'Discord' },
			{ id: 'integrations', label: 'INTEGRATIONS', route: '/integrations', icon: Cable, status: 'beta', ariaLabel: 'Integrations' }
		]
	},
	{
		pillar: 'SYSTEM',
		items: [
			{ id: 'control', label: 'CONTROL', route: '/control', icon: SlidersHorizontal, status: 'active', ariaLabel: 'System Control' }
		]
	}
];

/** Flat list (search, command palette, route generation). */
export const cockpitModules: CockpitModule[] = navSections.flatMap((s) => s.items);
