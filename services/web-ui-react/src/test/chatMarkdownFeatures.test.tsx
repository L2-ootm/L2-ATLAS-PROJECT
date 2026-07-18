import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ChatMarkdown } from '../components/ChatMarkdown';

describe('ChatMarkdown - Math Rendering', () => {
	it('renders inline math with KaTeX', () => {
		const { container } = render(<ChatMarkdown text="The value is $x + 3$ in the equation." />);
		const katex = container.querySelector('.katex');
		expect(katex).toBeTruthy();
	});

	it('renders display math with KaTeX', () => {
		const { container } = render(<ChatMarkdown text="$$\\frac{a}{b}$$" />);
		// KaTeX may render as .katex or .katex-display depending on context
		const katex = container.querySelector('.katex') || container.querySelector('.katex-display');
		expect(katex).toBeTruthy();
	});

	it('does not render math inside code blocks', () => {
		const { container } = render(<ChatMarkdown text={'```\n$x + 3$\n```'} />);
		const katex = container.querySelector('.katex');
		expect(katex).toBeFalsy();
	});

	it('renders inline code normally', () => {
		const { container } = render(<ChatMarkdown text="Use `console.log` for debugging." />);
		const code = container.querySelector('code');
		expect(code).toBeTruthy();
		expect(code?.textContent).toBe('console.log');
	});
});

describe('ChatMarkdown - Rich Formatting', () => {
	it('renders strikethrough text', () => {
		const { container } = render(<ChatMarkdown text="This is ~~deleted~~ text." />);
		const del = container.querySelector('del');
		expect(del).toBeTruthy();
		expect(del?.textContent).toBe('deleted');
	});

	it('renders task list items', () => {
		const { container } = render(<ChatMarkdown text="- [x] Done task\n- [ ] Todo task" />);
		// Task lists should render as list items
		const list = container.querySelector('ul');
		expect(list).toBeTruthy();
	});

	it('renders tables with alignment', () => {
		const text = `| Left | Center | Right |
|:---|:---:|---:|
| a | b | c |`;
		const { container } = render(<ChatMarkdown text={text} />);
		const table = container.querySelector('table');
		expect(table).toBeTruthy();
		const ths = container.querySelectorAll('th');
		expect(ths).toHaveLength(3);
	});

	it('renders blockquotes', () => {
		const { container } = render(<ChatMarkdown text="> This is a quote." />);
		const blockquote = container.querySelector('blockquote');
		expect(blockquote).toBeTruthy();
	});

	it('renders headings h1-h6', () => {
		const text = '# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6';
		const { container } = render(<ChatMarkdown text={text} />);
		expect(container.querySelector('h1')).toBeTruthy();
		expect(container.querySelector('h2')).toBeTruthy();
		expect(container.querySelector('h3')).toBeTruthy();
		expect(container.querySelector('h4')).toBeTruthy();
		expect(container.querySelector('h5')).toBeTruthy();
		expect(container.querySelector('h6')).toBeTruthy();
	});

	it('renders links with target blank', () => {
		const { container } = render(<ChatMarkdown text="[Example](https://example.com)" />);
		const link = container.querySelector('a');
		expect(link).toBeTruthy();
		expect(link?.getAttribute('target')).toBe('_blank');
		expect(link?.getAttribute('href')).toBe('https://example.com');
	});

	it('renders bold and italic', () => {
		const { container } = render(<ChatMarkdown text="**bold** and *italic*" />);
		const strong = container.querySelector('strong');
		const em = container.querySelector('em');
		expect(strong).toBeTruthy();
		expect(em).toBeTruthy();
	});

	it('renders horizontal rules', () => {
		const { container } = render(<ChatMarkdown text="---" />);
		const hr = container.querySelector('hr');
		expect(hr).toBeTruthy();
	});
});

describe('ChatMarkdown - MEDIA: Tags', () => {
	it('renders MEDIA: image tag as img element', () => {
		const { container } = render(<ChatMarkdown text="MEDIA:/path/to/image.png" />);
		const img = container.querySelector('img');
		expect(img).toBeTruthy();
		expect(img?.getAttribute('src')).toContain('/path/to/image.png');
	});

	it('renders MEDIA: video tag as video element', () => {
		const { container } = render(<ChatMarkdown text="MEDIA:/path/to/video.mp4" />);
		const video = container.querySelector('video');
		expect(video).toBeTruthy();
	});

	it('renders MEDIA: audio tag as audio element', () => {
		const { container } = render(<ChatMarkdown text="MEDIA:/path/to/audio.mp3" />);
		const audio = container.querySelector('audio');
		expect(audio).toBeTruthy();
	});
});

describe('ChatMarkdown - Code Blocks', () => {
	it('renders fenced code blocks with syntax highlighting', () => {
		const text = '```javascript\nconst x = 42;\n```';
		const { container } = render(<ChatMarkdown text={text} />);
		const pre = container.querySelector('pre');
		const code = container.querySelector('code');
		expect(pre).toBeTruthy();
		expect(code).toBeTruthy();
	});

	it('renders code block with copy button', () => {
		const text = '```\ncode here\n```';
		const { container } = render(<ChatMarkdown text={text} />);
		const copyButton = container.querySelector('button[title="Copy code"]');
		expect(copyButton).toBeTruthy();
	});
});
