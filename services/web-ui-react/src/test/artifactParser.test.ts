import { describe, it, expect } from 'vitest';
import { parseArtifacts } from '../components/ArtifactOverlay';

describe('parseArtifacts', () => {
	it('parses a single artifact with all metadata', () => {
		const text = `Some text before

\`\`\`atlas-artifact
type: code
title: Test Script
language: python
description: A test script
---
print("hello world")
\`\`\`

Some text after`;

		const { artifacts, cleanText } = parseArtifacts(text);

		expect(artifacts).toHaveLength(1);
		expect(artifacts[0].type).toBe('code');
		expect(artifacts[0].title).toBe('Test Script');
		expect(artifacts[0].language).toBe('python');
		expect(artifacts[0].description).toBe('A test script');
		expect(artifacts[0].content).toBe('print("hello world")');
		expect(cleanText).toContain('[Artifact: Test Script]');
		expect(cleanText).not.toContain('```atlas-artifact');
	});

	it('parses multiple artifacts', () => {
		const text = `\`\`\`atlas-artifact
type: html
title: Dashboard
---
<div>Hello</div>
\`\`\`

Middle text

\`\`\`atlas-artifact
type: data
title: Results
---
[{"a": 1}]
\`\`\``;

		const { artifacts } = parseArtifacts(text);

		expect(artifacts).toHaveLength(2);
		expect(artifacts[0].type).toBe('html');
		expect(artifacts[0].title).toBe('Dashboard');
		expect(artifacts[1].type).toBe('data');
		expect(artifacts[1].title).toBe('Results');
	});

	it('returns empty array when no artifacts present', () => {
		const text = 'Just regular markdown with **bold** and `code`';
		const { artifacts, cleanText } = parseArtifacts(text);

		expect(artifacts).toHaveLength(0);
		expect(cleanText).toBe(text);
	});

	it('skips malformed artifacts without separator', () => {
		const text = `\`\`\`atlas-artifact
type: code
title: Bad
no separator here
\`\`\``;

		const { artifacts } = parseArtifacts(text);
		expect(artifacts).toHaveLength(0);
	});

	it('skips artifacts without type', () => {
		const text = `\`\`\`atlas-artifact
title: No Type
---
content
\`\`\``;

		const { artifacts } = parseArtifacts(text);
		expect(artifacts).toHaveLength(0);
	});

	it('skips artifacts without content', () => {
		const text = `\`\`\`atlas-artifact
type: code
title: Empty
---
\`\`\``;

		const { artifacts } = parseArtifacts(text);
		expect(artifacts).toHaveLength(0);
	});

	it('generates unique IDs for each artifact', () => {
		const text = `\`\`\`atlas-artifact
type: code
title: A
---
content a
\`\`\`

\`\`\`atlas-artifact
type: code
title: B
---
content b
\`\`\``;

		const { artifacts } = parseArtifacts(text);
		expect(artifacts[0].id).not.toBe(artifacts[1].id);
	});

	it('handles artifacts with minimal metadata', () => {
		const text = `\`\`\`atlas-artifact
type: markdown
---
# Hello
\`\`\``;

		const { artifacts } = parseArtifacts(text);
		expect(artifacts).toHaveLength(1);
		expect(artifacts[0].type).toBe('markdown');
		expect(artifacts[0].title).toBe('Untitled Artifact');
	});
});
