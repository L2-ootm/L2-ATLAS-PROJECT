import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatMarkdown } from '../components/ChatMarkdown';

describe('ChatMarkdown', () => {
	it('renders bold and italic emphasis', () => {
		render(<ChatMarkdown text="This is **bold** and this is *italic*." />);
		expect(screen.getByText('bold').tagName).toBe('STRONG');
		expect(screen.getByText('italic').tagName).toBe('EM');
	});

	it('renders inline code without turning it into a fenced block', () => {
		render(<ChatMarkdown text="Run `npm run build` to build." />);
		const code = screen.getByText('npm run build');
		expect(code.tagName).toBe('CODE');
		expect(code.closest('pre')).toBeNull();
	});

	it('renders a fenced code block with a copy button and highlighted syntax', () => {
		const text = ['```ts', 'const x: number = 1;', '```'].join('\n');
		const { container } = render(<ChatMarkdown text={text} />);
		const code = container.querySelector('pre code');
		expect(code?.textContent).toContain('const x: number = 1;');
		// rehype-highlight tokenizes the line into semantic <span class="hljs-*"> runs.
		expect(code?.querySelector('.hljs-keyword')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /copy code/i })).toBeInTheDocument();
	});

	it('copies fenced code block contents to the clipboard on click', () => {
		const writeText = vi.fn().mockResolvedValue(undefined);
		Object.defineProperty(navigator, 'clipboard', {
			value: { writeText },
			configurable: true
		});
		const text = ['```', 'echo hello', '```'].join('\n');
		render(<ChatMarkdown text={text} />);

		fireEvent.click(screen.getByRole('button', { name: /copy code/i }));

		expect(writeText).toHaveBeenCalledWith(expect.stringContaining('echo hello'));
	});

	it('renders GFM tables', () => {
		const text = ['| A | B |', '| --- | --- |', '| 1 | 2 |'].join('\n');
		render(<ChatMarkdown text={text} />);
		expect(screen.getByRole('table')).toBeInTheDocument();
		expect(screen.getByText('1')).toBeInTheDocument();
		expect(screen.getByText('2')).toBeInTheDocument();
	});

	it('escapes raw HTML instead of executing it', () => {
		const raw = '<img src=x onerror="window.__pwned = true">';
		render(<ChatMarkdown text={raw} />);
		expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined();
	});

	it('never leaks a raw "node" attribute onto rendered DOM elements', () => {
		const text = '# Heading\n\nSome **text** with a [link](https://example.com).';
		const { container } = render(<ChatMarkdown text={text} />);
		expect(container.querySelector('[node]')).toBeNull();
	});
});
