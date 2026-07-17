import { AlertTriangle, RefreshCw } from 'lucide-react';
import { isRouteErrorResponse, useRouteError } from 'react-router-dom';

function errorDetail(error: unknown): string {
	if (isRouteErrorResponse(error)) return `${error.status} ${error.statusText}`.trim();
	if (error instanceof Error) return error.message;
	return 'The requested cockpit surface could not be loaded.';
}

export function RouteLoadError() {
	const error = useRouteError();
	return (
		<main className="atlas-route-error" data-topo="bad">
			<div className="atlas-route-error__signal" aria-hidden><AlertTriangle size={19} /></div>
			<div className="atlas-route-error__eyebrow">COCKPIT · RECOVERY</div>
			<h1>Surface unavailable</h1>
			<p>{errorDetail(error)}</p>
			<button type="button" onClick={() => window.location.reload()}>
				<RefreshCw size={13} /> Reload cockpit
			</button>
		</main>
	);
}
