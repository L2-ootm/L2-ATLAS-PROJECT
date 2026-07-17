import { Activity, Eye, Gauge, MoveDown } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import {
	loadVisualSettings,
	saveVisualSettings,
	type StreamIntensity,
	type StreamSpeed,
	type VisualSettings
} from '../../lib/visualSettings';

export function VisualsPanel() {
	const [settings, setSettings] = useState(loadVisualSettings);

	function patch(next: Partial<VisualSettings>) {
		const value = { ...settings, ...next };
		setSettings(value);
		saveVisualSettings(value);
	}

	return (
		<div className="atlas-visual-settings">
			<div className="atlas-visual-settings-intro">
				<div>
					<div className="atlas-visual-settings-kicker">RENDER PROTOCOL</div>
					<h2>Streaming response</h2>
					<p>Controls apply immediately to Chat and Console. Reduced-motion system preferences remain authoritative.</p>
				</div>
				<div className="atlas-visual-preview" data-enabled={settings.streamingEffect ? 'true' : 'false'}>
					<span>## LIVE OUTPUT</span>
					<div />
				</div>
			</div>

			<VisualSettingRow
				icon={<Activity size={15} />}
				label="SCAN EFFECT"
				detail="Chunk arrivals emit a short topographic scan across the live frontier."
			>
				<Toggle value={settings.streamingEffect} onChange={(value) => patch({ streamingEffect: value })} />
			</VisualSettingRow>
			<VisualSettingRow
				icon={<Gauge size={15} />}
				label="REVEAL SPEED"
				detail="Changes the paced character drain without changing the underlying response."
			>
				<Choice<StreamSpeed>
					value={settings.streamSpeed}
					options={['slow', 'balanced', 'fast']}
					onChange={(value) => patch({ streamSpeed: value })}
				/>
			</VisualSettingRow>
			<VisualSettingRow
				icon={<Eye size={15} />}
				label="SIGNAL INTENSITY"
				detail="Controls scan brightness and newest-block glow."
			>
				<Choice<StreamIntensity>
					value={settings.streamIntensity}
					options={['subtle', 'visible', 'high']}
					onChange={(value) => patch({ streamIntensity: value })}
				/>
			</VisualSettingRow>
			<VisualSettingRow
				icon={<MoveDown size={15} />}
				label="NEAR-BOTTOM FOLLOW"
				detail="Tracks growing responses only while the transcript remains near its latest edge."
			>
				<Toggle value={settings.autoFollow} onChange={(value) => patch({ autoFollow: value })} />
			</VisualSettingRow>
		</div>
	);
}

function VisualSettingRow({
	icon,
	label,
	detail,
	children
}: {
	icon: ReactNode;
	label: string;
	detail: string;
	children: ReactNode;
}) {
	return (
		<div className="atlas-visual-setting-row">
			<span className="atlas-visual-setting-icon">{icon}</span>
			<span className="atlas-visual-setting-copy">
				<strong>{label}</strong>
				<small>{detail}</small>
			</span>
			{children}
		</div>
	);
}

function Toggle({ value, onChange }: { value: boolean; onChange: (value: boolean) => void }) {
	return (
		<button
			type="button"
			className={`atlas-visual-toggle${value ? ' is-on' : ''}`}
			onClick={() => onChange(!value)}
			aria-pressed={value}
		>
			<span />
			{value ? 'ON' : 'OFF'}
		</button>
	);
}

function Choice<T extends string>({
	value,
	options,
	onChange
}: {
	value: T;
	options: T[];
	onChange: (value: T) => void;
}) {
	return (
		<div className="atlas-visual-choice">
			{options.map((option) => (
				<button
					type="button"
					key={option}
					className={value === option ? 'is-active' : ''}
					onClick={() => onChange(option)}
				>
					{option.toUpperCase()}
				</button>
			))}
		</div>
	);
}
