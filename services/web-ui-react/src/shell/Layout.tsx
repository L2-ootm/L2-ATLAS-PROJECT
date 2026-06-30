import { useCallback, useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import TopoField from '../components/TopoField';
import { GlassFilter } from '../components/GlassFx';
import MockModeBanner from '../components/MockModeBanner';
import { getConfig } from '../lib/api';
import {
	SIDEBAR_WIDTH_COLLAPSED,
	SIDEBAR_WIDTH_EXPANDED,
	SIDEBAR_STORAGE_KEY
} from '../lib/ui-state';
import { AgentSurfaceProvider } from '../context/AgentSurfaceContext';
import AgentSessionHeader from '../components/agent/AgentSessionHeader';
import PermissionQueueSidebar from '../components/agent/PermissionQueueSidebar';

// ── Shell layout — living terrain behind, fixed sidebar, offset content ──────
export default function Layout() {
	const [expanded, setExpanded] = useState(false);
	const [mockMode, setMockMode] = useState(false);

	useEffect(() => {
		const saved = localStorage.getItem(SIDEBAR_STORAGE_KEY);
		if (saved !== null) setExpanded(saved === 'true');
	}, []);

	useEffect(() => {
		// Gateway-offline / pre-mock_mode gateway both degrade to no banner —
		// the absence of a live signal must never read as "mock mode on".
		getConfig()
			.then((cfg) => setMockMode(cfg.mock_mode ?? false))
			.catch(() => setMockMode(false));
	}, []);

	const toggle = useCallback(() => {
		setExpanded((prev) => {
			const next = !prev;
			localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
			return next;
		});
	}, []);

	const offset = expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED;

	return (
		<AgentSurfaceProvider>
			<TopoField />
			<GlassFilter />
			<div style={{ display: 'flex', minHeight: '100vh', position: 'relative', zIndex: 1 }}>
				<Sidebar expanded={expanded} onToggle={toggle} />
				<main
					id="main-content"
					style={{
						flex: 1,
						marginLeft: offset,
						overflowY: 'auto',
						padding: '24px 32px',
						minHeight: '100vh',
						transition: 'margin-left 150ms var(--l2-ease)'
					}}
				>
					<MockModeBanner mockMode={mockMode} />
					<AgentSessionHeader />
					<Outlet />
				</main>
				<PermissionQueueSidebar />
			</div>
		</AgentSurfaceProvider>
	);
}
