import { readFile, readdir } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const BUDGETS = {
	entry: { rawBytes: 350_000, gzipBytes: 100_000, label: 'entry' },
	react: { rawBytes: 300_000, gzipBytes: 100_000, label: 'React vendor' },
	graph: { rawBytes: 1_400_000, gzipBytes: 400_000, label: 'graph vendor' },
	other: { rawBytes: 500_000, label: 'other chunk' }
};

export function classifyChunk(name) {
	if (/^index-[^.]+\.js$/.test(name)) return 'entry';
	if (/^vendor-react-[^.]+\.js$/.test(name)) return 'react';
	if (/^vendor-force-graph-[^.]+\.js$/.test(name)) return 'graph';
	return 'other';
}

function formatKilobytes(bytes) {
	return `${(bytes / 1000).toFixed(2)} KB`;
}

export function evaluateBundle(chunks) {
	const violations = [];
	const present = new Set();
	const reports = chunks.map((chunk) => {
		const kind = classifyChunk(chunk.name);
		const budget = BUDGETS[kind];
		present.add(kind);
		if (chunk.rawBytes > budget.rawBytes) {
			violations.push(
				`${kind === 'other' ? chunk.name : budget.label} raw ${formatKilobytes(chunk.rawBytes)} exceeds ${formatKilobytes(budget.rawBytes)}`
			);
		}
		if (budget.gzipBytes !== undefined && chunk.gzipBytes > budget.gzipBytes) {
			violations.push(
				`${budget.label} gzip ${formatKilobytes(chunk.gzipBytes)} exceeds ${formatKilobytes(budget.gzipBytes)}`
			);
		}
		return { ...chunk, kind };
	});

	for (const [kind, label] of [
		['entry', 'entry'],
		['react', 'React vendor'],
		['graph', 'graph vendor']
	]) {
		if (!present.has(kind)) violations.push(`missing ${label} chunk`);
	}

	return { reports, violations };
}

async function readBundleChunks(distDirectory) {
	const assetsDirectory = join(distDirectory, 'assets');
	const names = (await readdir(assetsDirectory))
		.filter((name) => name.endsWith('.js'))
		.sort();
	return Promise.all(
		names.map(async (name) => {
			const content = await readFile(join(assetsDirectory, name));
			return {
				name,
				rawBytes: content.byteLength,
				gzipBytes: gzipSync(content).byteLength
			};
		})
	);
}

async function main() {
	const scriptDirectory = dirname(fileURLToPath(import.meta.url));
	const distDirectory = resolve(process.argv[2] ?? join(scriptDirectory, '..', 'dist'));
	const result = evaluateBundle(await readBundleChunks(distDirectory));

	for (const report of result.reports) {
		console.log(
			`${report.name}: ${formatKilobytes(report.rawBytes)} raw / ${formatKilobytes(report.gzipBytes)} gzip`
		);
	}
	if (result.violations.length > 0) {
		for (const violation of result.violations) console.error(`BUDGET: ${violation}`);
		process.exitCode = 1;
	}
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : '';
if (invokedPath === fileURLToPath(import.meta.url)) {
	await main();
}
