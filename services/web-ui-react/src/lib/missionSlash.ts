export type MissionSlashIntent =
	| { kind: 'goal-launch'; objective: string }
	| { kind: 'goal-status' };

export const GOAL_STATUS_MESSAGE = 'Long-horizon mission status is available in Missions.';

/** Parse WebUI-only long-horizon aliases without consuming ordinary prompts. */
export function parseMissionSlashIntent(input: string): MissionSlashIntent | null {
	const match = input.trim().match(/^\/(?:goal|mission)(?:\s+([\s\S]*))?$/);
	if (!match) return null;
	const objective = (match[1] ?? '').trim();
	if (objective === '' || objective === 'status') return { kind: 'goal-status' };
	return { kind: 'goal-launch', objective };
}
