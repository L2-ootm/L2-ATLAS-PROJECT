export type ScrollMetrics = {
	scrollHeight: number;
	scrollTop: number;
	clientHeight: number;
};

export function distanceFromBottom(metrics: ScrollMetrics): number {
	return Math.max(0, metrics.scrollHeight - metrics.scrollTop - metrics.clientHeight);
}

export function isNearBottom(metrics: ScrollMetrics, threshold = 180): boolean {
	return distanceFromBottom(metrics) <= threshold;
}
