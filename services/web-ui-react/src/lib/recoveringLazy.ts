import { lazy, type ComponentType, type LazyExoticComponent } from 'react';

const CHUNK_ERROR = /failed to fetch dynamically imported module|importing a module script failed|error loading dynamically imported module/i;
const MARKER_PREFIX = 'atlas.chunk-recovery.';

type RecoveryEnvironment = {
	get: (key: string) => string | null;
	set: (key: string, value: string) => void;
	remove: (key: string) => void;
	reload: () => void;
};

function browserEnvironment(): RecoveryEnvironment {
	return {
		get: (key) => window.sessionStorage.getItem(key),
		set: (key, value) => window.sessionStorage.setItem(key, value),
		remove: (key) => window.sessionStorage.removeItem(key),
		reload: () => window.location.reload()
	};
}

export function isStaleChunkError(error: unknown): boolean {
	return error instanceof Error && CHUNK_ERROR.test(error.message);
}

/**
 * Recover once when an open page references a hashed lazy chunk removed by a
 * newer build. The unresolved promise prevents React Router from painting its
 * error UI during the navigation that is about to reload the document.
 */
export async function loadWithChunkRecovery<T>(
	key: string,
	loader: () => Promise<T>,
	environment: RecoveryEnvironment = browserEnvironment()
): Promise<T> {
	const marker = `${MARKER_PREFIX}${key}`;
	try {
		const loaded = await loader();
		environment.remove(marker);
		return loaded;
	} catch (error) {
		if (!isStaleChunkError(error) || environment.get(marker)) throw error;
		environment.set(marker, '1');
		environment.reload();
		return await new Promise<T>(() => undefined);
	}
}

export function recoveringLazy(
	key: string,
	loader: () => Promise<{ default: ComponentType }>
): LazyExoticComponent<ComponentType> {
	return lazy(() => loadWithChunkRecovery(key, loader));
}
