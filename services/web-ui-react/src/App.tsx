import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import Layout from './shell/Layout';
import Dashboard from './routes/Dashboard';
import Missions from './routes/Missions';
import MissionDetail from './routes/MissionDetail';
import Runs from './routes/Runs';
import RunDetail from './routes/RunDetail';
import Command from './routes/Command';
import Projects from './routes/Projects';
import Control from './routes/Control';
import Discord from './routes/Discord';
import Cashflow from './routes/Cashflow';
import Ledger from './routes/Ledger';
import Codex from './routes/Codex';
import Models from './routes/Models';
import Integrations from './routes/Integrations';
import Migrating from './routes/Migrating';

// Lazy — pulls three.js, kept out of the main bundle.
const Graph = lazy(() => import('./routes/Graph'));
// Lazy — pulls the markdown/highlight stack, kept out of the main bundle.
const Console = lazy(() => import('./routes/Console'));

const router = createBrowserRouter([
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
			{ path: 'console', element: <Suspense fallback={null}><Console /></Suspense> },
			{ path: 'graph', element: <Suspense fallback={null}><Graph /></Suspense> },
			{ path: 'projects', element: <Projects /> },
			{ path: 'cashflow', element: <Cashflow /> },
			{ path: 'audit', element: <Ledger /> },
			{ path: 'wiki', element: <Codex /> },
			{ path: 'models', element: <Models /> },
			{ path: 'integrations', element: <Integrations /> },
			{ path: 'discord', element: <Discord /> },
			{ path: 'control', element: <Control /> },
			// Compatibility shims — Settings and System merged into /control.
			{ path: 'system', element: <Navigate to="/control" replace /> },
			{ path: 'settings', element: <Navigate to="/control?tab=provider" replace /> },
			{ path: '*', element: <Migrating pillar="ATLAS" name="Not Found" /> }
		]
	}
]);

export default function App() {
	return <RouterProvider router={router} />;
}
