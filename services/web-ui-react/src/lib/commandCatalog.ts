import { listModuleCommands } from './api';
import { ATLAS_COMMANDS, type AtlasCommand } from './atlasCommands';

let catalogPromise: Promise<AtlasCommand[]> | null = null;

/** One catalog for modal and inline slash surfaces. Built-ins reserve names. */
export function loadAtlasCommandCatalog(): Promise<AtlasCommand[]> {
	if (!catalogPromise) {
		catalogPromise = listModuleCommands().then((modules) => {
			const names = new Set(ATLAS_COMMANDS.map((command) => command.name));
			const contributed = modules
				.filter((command) => !names.has(command.name))
				.map((command) => ({ ...command, source: 'module' as const }));
			return [...ATLAS_COMMANDS, ...contributed];
		});
	}
	return catalogPromise;
}

export function resetAtlasCommandCatalogForTests(): void {
	catalogPromise = null;
}
