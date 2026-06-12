import type { Component } from 'svelte';
import type { LucideProps } from '@lucide/svelte';

export type ModuleStatus = 'active' | 'beta' | 'planned';

export interface CockpitModule {
	id: string;
	label: string;
	route: string;
	icon: Component<LucideProps>;
	status: ModuleStatus;
	ariaLabel: string;
}

// Registry is the single source of truth for sidebar navigation.
// Future modules register here — no shell rewiring required.
// Each entry must have a corresponding route under src/routes/.
import { Activity, BookOpen, Cpu, Map } from '@lucide/svelte';

export const cockpitModules: CockpitModule[] = [
	{
		id: 'missions',
		label: 'MISSIONS',
		route: '/missions',
		icon: Map,
		status: 'active',
		ariaLabel: 'Missions'
	},
	{
		id: 'runs',
		label: 'RUNS',
		route: '/runs',
		icon: Activity,
		status: 'active',
		ariaLabel: 'Runs'
	},
	{
		id: 'wiki',
		label: 'WIKI',
		route: '/wiki',
		icon: BookOpen,
		status: 'active',
		ariaLabel: 'Wiki'
	},
	{
		id: 'models',
		label: 'MODELS',
		route: '/models',
		icon: Cpu,
		status: 'active',
		ariaLabel: 'Model Registry'
	}
];
