import type { RunWithMission } from './api';

export type RunSessionGroup = {
	id: string;
	runs: RunWithMission[];
	latest: RunWithMission;
	oldest: RunWithMission;
	status: string;
	active: boolean;
};

function sessionStatus(runs: RunWithMission[]): string {
	const states = new Set(runs.map((run) => run.status.toUpperCase()));
	if (states.has('RUNNING')) return 'RUNNING';
	if (states.has('PENDING')) return 'PENDING';
	if (states.size === 1) return runs[0].status;
	if (states.has('FAILED')) return 'PARTIAL';
	return runs[0].status;
}

export function groupRunsBySession(runs: RunWithMission[]): RunSessionGroup[] {
	const buckets = new Map<string, RunWithMission[]>();
	for (const run of runs) {
		// Legacy runs without a session id remain individually addressable and
		// must never be collapsed into one fake null session.
		const id = run.session_id ?? `run:${run.id}`;
		const bucket = buckets.get(id);
		if (bucket) bucket.push(run);
		else buckets.set(id, [run]);
	}

	return [...buckets.entries()]
		.map(([id, members]) => {
			const ordered = [...members].sort(
				(a, b) => Date.parse(b.started_at) - Date.parse(a.started_at)
			);
			const status = sessionStatus(ordered);
			return {
				id,
				runs: ordered,
				latest: ordered[0],
				oldest: ordered[ordered.length - 1],
				status,
				active: status.toUpperCase() === 'RUNNING' || status.toUpperCase() === 'PENDING'
			};
		})
		.sort((a, b) => Date.parse(b.latest.started_at) - Date.parse(a.latest.started_at));
}
