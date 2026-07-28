/** Binary-content guard that samples the first ~1KB. */
export function looksBinary(content: string): boolean {
	const sample = content.slice(0, 1024);
	if (sample.length === 0) return false;

	let nonPrintable = 0;
	for (let i = 0; i < sample.length; i++) {
		const code = sample.charCodeAt(i);
		if (code === 0) return true;
		if (code < 32 && code !== 9 && code !== 10 && code !== 13) {
			nonPrintable++;
		}
	}

	return nonPrintable / sample.length > 0.3;
}
