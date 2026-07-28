export interface Artifact {
	id: string;
	type: 'html' | 'code' | 'markdown' | 'image' | 'data';
	title: string;
	content: string;
	language?: string;
	description?: string;
}

/** Parse atlas-artifact code blocks from markdown text. */
export function parseArtifacts(text: string): { artifacts: Artifact[]; cleanText: string } {
	const artifacts: Artifact[] = [];
	const regex = /```atlas-artifact\n([\s\S]*?)\n```/g;
	let match;
	let cleanText = text;

	while ((match = regex.exec(text)) !== null) {
		const block = match[1];
		const separatorIndex = block.indexOf('---');
		if (separatorIndex === -1) continue;

		const headerPart = block.slice(0, separatorIndex).trim();
		const content = block.slice(separatorIndex + 3).trim();

		// Parse YAML-like frontmatter
		const meta: Record<string, string> = {};
		for (const line of headerPart.split('\n')) {
			const colonIndex = line.indexOf(':');
			if (colonIndex > 0) {
				const key = line.slice(0, colonIndex).trim();
				const value = line.slice(colonIndex + 1).trim();
				meta[key] = value;
			}
		}

		if (meta.type && content) {
			artifacts.push({
				id: `art-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
				type: meta.type as Artifact['type'],
				title: meta.title || 'Untitled Artifact',
				content,
				language: meta.language,
				description: meta.description
			});
			cleanText = cleanText.replace(match[0], `[Artifact: ${meta.title || 'Untitled'}]`);
		}
	}

	return { artifacts, cleanText };
}
