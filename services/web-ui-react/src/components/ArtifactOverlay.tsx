import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { X, Copy, Download, Maximize2, Minimize2, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface Artifact {
	id: string;
	type: 'html' | 'code' | 'markdown' | 'image' | 'data';
	title: string;
	content: string;
	language?: string;
	description?: string;
}

interface ArtifactOverlayProps {
	artifact: Artifact;
	onClose: () => void;
}

export function ArtifactOverlay({ artifact, onClose }: ArtifactOverlayProps) {
	const [copied, setCopied] = useState(false);
	const [expanded, setExpanded] = useState(false);

	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === 'Escape') onClose();
		};
		window.addEventListener('keydown', handleEscape);
		return () => window.removeEventListener('keydown', handleEscape);
	}, [onClose]);

	async function copyContent() {
		await navigator.clipboard.writeText(artifact.content);
		setCopied(true);
		setTimeout(() => setCopied(false), 1400);
	}

	function downloadContent() {
		const mimeTypes: Record<string, string> = {
			html: 'text/html',
			code: 'text/plain',
			markdown: 'text/markdown',
			image: 'image/png',
			data: 'application/json'
		};
		const extensions: Record<string, string> = {
			html: 'html',
			code: artifact.language || 'txt',
			markdown: 'md',
			image: 'png',
			data: 'json'
		};
		const blob = new Blob([artifact.content], { type: mimeTypes[artifact.type] || 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `${artifact.title}.${extensions[artifact.type] || 'txt'}`;
		a.click();
		URL.revokeObjectURL(url);
	}

	return (
		<div
			onClick={onClose}
			style={{
				position: 'fixed',
				inset: 0,
				zIndex: 300,
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'center',
				background: 'rgba(5,6,10,0.82)',
				backdropFilter: 'blur(8px)',
				WebkitBackdropFilter: 'blur(8px)'
			}}
		>
			<div
				onClick={(e) => e.stopPropagation()}
				style={{
					position: 'relative',
					width: expanded ? '95vw' : 'min(900px, 90vw)',
					height: expanded ? '95vh' : 'min(700px, 85vh)',
					display: 'flex',
					flexDirection: 'column',
					borderRadius: 2,
					border: '1px solid rgba(237,234,224,0.10)',
					background: 'linear-gradient(160deg, rgba(20,24,33,0.98), rgba(10,12,18,0.98))',
					boxShadow: '0 28px 90px rgba(0,0,0,0.58)',
					overflow: 'hidden',
					transition: 'width 0.2s, height 0.2s'
				}}
			>
				{/* Header */}
				<div style={{
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'space-between',
					padding: '10px 16px',
					borderBottom: '1px solid rgba(237,234,224,0.08)',
					flexShrink: 0
				}}>
					<div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
						<span style={{
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 10,
							letterSpacing: '0.14em',
							color: 'var(--atlas-celestial)',
							textTransform: 'uppercase'
						}}>
							{artifact.type}
						</span>
						<span style={{
							fontSize: 14,
							fontWeight: 600,
							color: 'var(--l2-fg-1)'
						}}>
							{artifact.title}
						</span>
						{artifact.language && (
							<span style={{
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 10,
								color: 'var(--l2-fg-3)',
								padding: '2px 6px',
								borderRadius: 2,
								border: '1px solid rgba(237,234,224,0.10)'
							}}>
								{artifact.language}
							</span>
						)}
					</div>
					<div style={{ display: 'flex', gap: 6 }}>
						<ActionButton onClick={copyContent} title="Copy">
							{copied ? <Check size={14} /> : <Copy size={14} />}
						</ActionButton>
						<ActionButton onClick={downloadContent} title="Download">
							<Download size={14} />
						</ActionButton>
						<ActionButton onClick={() => setExpanded(!expanded)} title={expanded ? 'Shrink' : 'Expand'}>
							{expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
						</ActionButton>
						<ActionButton onClick={onClose} title="Close">
							<X size={14} />
						</ActionButton>
					</div>
				</div>

				{/* Content */}
				<div style={{ flex: 1, overflow: 'auto', padding: artifact.type === 'html' ? 0 : 16 }}>
					<ArtifactContent artifact={artifact} />
				</div>

				{/* Description footer */}
				{artifact.description && (
					<div style={{
						padding: '8px 16px',
						borderTop: '1px solid rgba(237,234,224,0.06)',
						fontSize: 12,
						color: 'var(--l2-fg-3)',
						flexShrink: 0
					}}>
						{artifact.description}
					</div>
				)}
			</div>
		</div>
	);
}

function ActionButton({ children, onClick, title }: { children: ReactNode; onClick: () => void; title: string }) {
	return (
		<button
			type="button"
			onClick={onClick}
			title={title}
			aria-label={title}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				justifyContent: 'center',
				width: 28,
				height: 28,
				borderRadius: 2,
				border: '1px solid rgba(237,234,224,0.10)',
				background: 'transparent',
				color: 'var(--l2-fg-3)',
				cursor: 'pointer',
				transition: 'border-color 0.15s, color 0.15s'
			}}
			onMouseEnter={(e) => {
				e.currentTarget.style.borderColor = 'rgba(70,240,160,0.4)';
				e.currentTarget.style.color = 'var(--l2-fg-1)';
			}}
			onMouseLeave={(e) => {
				e.currentTarget.style.borderColor = 'rgba(237,234,224,0.10)';
				e.currentTarget.style.color = 'var(--l2-fg-3)';
			}}
		>
			{children}
		</button>
	);
}

function ArtifactContent({ artifact }: { artifact: Artifact }) {
	switch (artifact.type) {
		case 'html':
			return (
				<iframe
					sandbox="allow-scripts allow-same-origin"
					srcDoc={artifact.content}
					style={{ width: '100%', height: '100%', border: 'none' }}
					title={artifact.title}
				/>
			);

		case 'code':
			return (
				<pre style={{
					margin: 0,
					fontFamily: 'var(--l2-font-mono)',
					fontSize: 13,
					lineHeight: 1.55,
					color: 'var(--l2-fg-1)',
					whiteSpace: 'pre',
					tabSize: 2
				}}>
					<code>{artifact.content}</code>
				</pre>
			);

		case 'markdown':
			return (
				<div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--l2-fg-1)' }}>
					<ReactMarkdown remarkPlugins={[remarkGfm]}>
						{artifact.content}
					</ReactMarkdown>
				</div>
			);

		case 'image':
			return (
				<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
					<img
						src={artifact.content}
						alt={artifact.title}
						style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
					/>
				</div>
			);

		case 'data':
			return <DataRenderer content={artifact.content} />;

		default:
			return <pre style={{ color: 'var(--l2-fg-2)' }}>{artifact.content}</pre>;
	}
}

function DataRenderer({ content }: { content: string }) {
	try {
		const data = JSON.parse(content);
		if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object') {
			const headers = Object.keys(data[0]);
			return (
				<div style={{ overflow: 'auto' }}>
					<table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12.5 }}>
						<thead>
							<tr>
								{headers.map((h) => (
									<th key={h} style={{
										textAlign: 'left',
										padding: '6px 10px',
										fontFamily: 'var(--l2-font-mono)',
										fontSize: 10.5,
										letterSpacing: '0.08em',
										color: 'var(--l2-fg-2)',
										background: 'rgba(13,16,24,0.65)',
										borderBottom: '1px solid rgba(237,234,224,0.10)'
									}}>
										{h}
									</th>
								))}
							</tr>
						</thead>
						<tbody>
							{data.map((row: any, i: number) => (
								<tr key={i}>
									{headers.map((h) => (
										<td key={h} style={{
											padding: '6px 10px',
											borderBottom: '1px solid rgba(237,234,224,0.06)',
											color: 'var(--l2-fg-1)'
										}}>
											{typeof row[h] === 'object' ? JSON.stringify(row[h]) : String(row[h] ?? '')}
										</td>
									))}
								</tr>
							))}
						</tbody>
					</table>
				</div>
			);
		}
		// JSON tree view for non-array data
		return (
			<pre style={{
				margin: 0,
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 13,
				lineHeight: 1.55,
				color: 'var(--l2-fg-1)',
				whiteSpace: 'pre-wrap'
			}}>
				{JSON.stringify(data, null, 2)}
			</pre>
		);
	} catch {
		return <pre style={{ color: 'var(--l2-fg-2)' }}>{content}</pre>;
	}
}

/** Parse atlas-artifact code blocks from markdown text */
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
