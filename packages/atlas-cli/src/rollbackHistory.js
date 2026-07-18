'use strict';

const MAX_ROLLBACK_HISTORY = 20;

/**
 * Append a rollback entry to the history array in install state.
 * Trims to MAX_ROLLBACK_HISTORY entries (newest first).
 */
function appendRollbackHistory(state, from, to, reason = 'explicit') {
	const entry = {
		from,
		to,
		timestamp: new Date().toISOString(),
		reason
	};
	const history = Array.isArray(state.rollbackHistory) ? state.rollbackHistory : [];
	history.unshift(entry);
	if (history.length > MAX_ROLLBACK_HISTORY) {
		history.length = MAX_ROLLBACK_HISTORY;
	}
	return { ...state, rollbackHistory: history };
}

/** Return the rollback history array, newest first. Empty array if none. */
function getRollbackHistory(state) {
	return Array.isArray(state?.rollbackHistory) ? state.rollbackHistory : [];
}

/**
 * Resolve the target version for a rollback.
 * Priority: explicit --to > history chain (first entry's `from`) > previousVersion.
 */
function resolveRollbackTarget(state, explicitTarget) {
	if (explicitTarget) return explicitTarget;
	// History chain: if we previously rolled from X to Y, rolling back again
	// should go back to X (the version before Y).
	const history = getRollbackHistory(state);
	if (history.length > 0) {
		return history[0].from;
	}
	// Legacy single-slot fallback (state predates rollbackHistory).
	return state?.previousVersion || null;
}

module.exports = { appendRollbackHistory, getRollbackHistory, resolveRollbackTarget, MAX_ROLLBACK_HISTORY };
