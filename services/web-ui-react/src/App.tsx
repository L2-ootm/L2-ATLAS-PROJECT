import { lazy, Suspense } from 'react';
import { type RouteObject } from 'react-router-dom';
import Layout from './shell/Layout';
import Dashboard from './routes/Dashboard';
import Missions from './routes/Missions';
import MissionDetail from './routes/MissionDetail';
import Runs from './routes/Runs';
import RunDetail from './routes/RunDetail';
import Console from './routes/Console';
import Command from './routes/Command';
import Projects from './routes/Projects';
import System from './routes/System';
import Discord from './routes/Discord';
import Cashflow from './routes/Cashflow';
import Ledger from './routes/Ledger';
import Codex from './routes/Codex';
import Models from './routes/Models';
import Integrations from './routes/Integrations';
import Migrating from './routes/Migrating';

// Lazy — pulls three.js, kept out of the main bundle.
const Graph = lazy(() => import('./routes/Graph'));

// Route manifest. Surfaces marked <Migrating> are still served by the Svelte
// cockpit and are being ported into the React shell route-by-route.
export const routes: RouteObject[] = [
	{
		path: '/',
		element: <Layout />,
		children: [
			{ index: true, element: <Dashboard /> },
			{ path: 'command', element: <Command /> },
			{ path: 'missions', element: <Missions /> },
			{ path: 'missions/:id', element: <MissionDetail /> },
			{ path: 'runs', element: <Runs /> },
			{ path: 'runs/:id', element: <RunDetail /> },
			{ path: 'console', element: <Console /> },
			{ path: 'graph', element: <Suspense fallback={null}><Graph /></Suspense> },
			{ path: 'projects', element: <Projects /> },
			{ path: 'cashflow', element: <Cashflow /> },
			{ path: 'audit', element: <Ledger /> },
			{ path: 'wiki', element: <Codex /> },
			{ path: 'models', element: <Models /> },
			{ path: 'integrations', element: <Integrations /> },
			{ path: 'discord', element: <Discord /> },
			{ path: 'system', element: <System /> },
			{ path: '*', element: <Migrating pillar="ATLAS" name="Not Found" /> }
		]
	}
];
