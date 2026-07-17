import { useEffect, useState } from 'react';

export type StreamSpeed = 'slow' | 'balanced' | 'fast';
export type StreamIntensity = 'subtle' | 'visible' | 'high';

export interface VisualSettings {
	streamingEffect: boolean;
	streamSpeed: StreamSpeed;
	streamIntensity: StreamIntensity;
	autoFollow: boolean;
}

const STORAGE_KEY = 'atlas.visual-settings.v1';
const CHANGE_EVENT = 'atlas-visual-settings-change';

export const DEFAULT_VISUAL_SETTINGS: VisualSettings = {
	streamingEffect: true,
	streamSpeed: 'balanced',
	streamIntensity: 'visible',
	autoFollow: true
};

export function loadVisualSettings(): VisualSettings {
	if (typeof window === 'undefined') return DEFAULT_VISUAL_SETTINGS;
	try {
		const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<VisualSettings>;
		return {
			streamingEffect:
				typeof parsed.streamingEffect === 'boolean'
					? parsed.streamingEffect
					: DEFAULT_VISUAL_SETTINGS.streamingEffect,
			streamSpeed:
				parsed.streamSpeed === 'slow' || parsed.streamSpeed === 'fast'
					? parsed.streamSpeed
					: 'balanced',
			streamIntensity:
				parsed.streamIntensity === 'subtle' || parsed.streamIntensity === 'high'
					? parsed.streamIntensity
					: 'visible',
			autoFollow:
				typeof parsed.autoFollow === 'boolean'
					? parsed.autoFollow
					: DEFAULT_VISUAL_SETTINGS.autoFollow
		};
	} catch {
		return DEFAULT_VISUAL_SETTINGS;
	}
}

export function saveVisualSettings(settings: VisualSettings): void {
	if (typeof window === 'undefined') return;
	localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
	window.dispatchEvent(new CustomEvent<VisualSettings>(CHANGE_EVENT, { detail: settings }));
}

export function useVisualSettings(): VisualSettings {
	const [settings, setSettings] = useState(loadVisualSettings);
	useEffect(() => {
		const update = (event: Event) => {
			const custom = event as CustomEvent<VisualSettings>;
			setSettings(custom.detail ?? loadVisualSettings());
		};
		const storage = (event: StorageEvent) => {
			if (event.key === STORAGE_KEY) setSettings(loadVisualSettings());
		};
		window.addEventListener(CHANGE_EVENT, update);
		window.addEventListener('storage', storage);
		return () => {
			window.removeEventListener(CHANGE_EVENT, update);
			window.removeEventListener('storage', storage);
		};
	}, []);
	return settings;
}

export function streamSpeedMultiplier(speed: StreamSpeed): number {
	if (speed === 'slow') return 0.62;
	if (speed === 'fast') return 1.65;
	return 1;
}

export function streamIntensityValue(intensity: StreamIntensity): number {
	if (intensity === 'subtle') return 0.48;
	if (intensity === 'high') return 1.35;
	return 0.88;
}

