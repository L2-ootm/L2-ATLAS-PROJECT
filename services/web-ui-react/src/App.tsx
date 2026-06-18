import { type RouteObject } from 'react-router-dom';
import Layout from './shell/Layout';
import Dashboard from './routes/Dashboard';
import Missions from './routes/Missions';
import MissionDetail from './routes/MissionDetail';
import Runs from './routes/Runs';
import RunDetail from './routes/RunDetail';
import Console from './routes/Console';
import Projects from './routes/Projects';
import System from './routes/System';
import Cashflow from './routes/Cashflow';
import Migrating from './routes/Migrating';

// Route manifest. Surfaces marked <Migrating> are still served by the Svelte
// cockpit and are being ported into the React shell route-by-route.
export const routes: RouteObject[] = [
	{
		path: '/',
		element: <Layout />,
		children: [
			{ index: true, element: <Dashboard /> },
			{ path: 'missions', element: <Missions /> },
			{ path: 'missions/:id', element: <MissionDetail /> },
			{ path: 'runs', element: <Runs /> },
			{ path: 'runs/:id', element: <RunDetail /> },
			{ path: 'console', element: <Console /> },
			{ path: 'projects', element: <Projects /> },
			{ path: 'cashflow', element: <Cashflow /> },
			{ path: 'audit', element: <Migrating pillar="AUDIT" name="Ledger" /> },
			{ path: 'wiki', element: <Migrating pillar="STRUCTURE" name="Codex" /> },
			{ path: 'models', element: <Migrating pillar="STRUCTURE" name="Models" /> },
			{ path: 'integrations', element: <Migrating pillar="STRUCTURE" name="Integrations" /> },
			{ path: 'system', element: <System /> },
			{ path: '*', element: <Migrating pillar="ATLAS" name="Not Found" /> }
		]
	}
];
