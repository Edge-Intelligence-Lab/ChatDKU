import { marked } from 'marked';

// Mock DOM for testing
Object.defineProperty(window, 'document', {
  writable: true,
  configurable: true,
  value: {
    createElement: jest.fn(() => ({
      id: '',
      innerHTML: '',
      className: '',
      style: {},
      appendChild: jest.fn(),
      setAttribute: jest.fn(),
      classList: {
        add: jest.fn(),
        remove: jest.fn(),
        contains: jest.fn(),
      },
      offsetHeight: 0,
      querySelector: jest.fn(),
      querySelectorAll: jest.fn(() => []),
    })),
    getElementById: jest.fn(() => null),
    head: {
      appendChild: jest.fn(),
    },
    body: {
      appendChild: jest.fn(),
    },
  },
});

// Mock the ChatPage functions that handle markdown and streaming
const configureMarked = () => {
  marked.setOptions({
    breaks: true,
    gfm: true,
  });
};

const parseMarkdown = (content: string): string => {
  if (!content) return "";
  const cleanedContent = content.replace(/<think>[\s\S]*?<\/think>/gi, "");
  const parsed = marked.parse(cleanedContent) as any;
  if (typeof parsed?.then === "function") {
    return cleanedContent;
  }
  return typeof parsed === "string" && parsed.trim().length > 0
    ? parsed
    : cleanedContent;
};

const streamText = async (
  text: string,
  elementContainer: HTMLElement,
  chunkDelayMs = 60,
) => {
  const cleanedText = text.replace(/<think>[\s\S]*?<\/think>/gi, "");

  // Mock stream container creation
  const streamContainer = {
    className: "",
    innerHTML: "",
    appendChild: jest.fn(),
  } as any;

  // Prefer paragraph chunks; fallback to sentences if only one paragraph
  const paragraphs = cleanedText
    .split(/\n{2,}/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  let chunks: string[] = [];
  if (paragraphs.length > 1) {
    chunks = paragraphs;
  } else {
    const sentences = cleanedText.match(/[^\r\n.!?]+[.!?]*(?:\s+|$)/g) || [
      cleanedText,
    ];
    chunks = sentences.map((s) => s.trim()).filter((s) => s.length > 0);
  }

  // Stream each chunk as parsed markdown
  for (const chunk of chunks) {
    const chunkHTML = parseMarkdown(chunk);
    (streamContainer as any).innerHTML += chunkHTML;
    await new Promise((resolve) => setTimeout(resolve, chunkDelayMs));
  }

  return streamContainer;
};

describe('Markdown and Streaming Utilities', () => {
  beforeEach(() => {
    configureMarked();
    jest.clearAllMocks();
  });

  describe('parseMarkdown', () => {
    it('parses basic markdown', () => {
      const input = "# Heading\n\nThis is **bold** text.";
      const result = parseMarkdown(input);

      expect(result).toContain('<h1');
      expect(result).toContain('<strong');
      expect(result).toContain('bold');
    });

    it('handles empty input', () => {
      const result = parseMarkdown("");
      expect(result).toBe("");
    });

    it('removes thinking tags', () => {
      const input = "Normal text<think>Internal reasoning</think>More text";
      const result = parseMarkdown(input);

      expect(result).not.toContain('<think>');
      expect(result).not.toContain('Internal reasoning');
      expect(result).toContain('Normal text');
      expect(result).toContain('More text');
    });

    it('handles multiline thinking tags', () => {
      const input = "Start<think>\nMulti-line\nthinking\n</think>End";
      const result = parseMarkdown(input);

      expect(result).not.toContain('<think>');
      expect(result).toContain('Start');
      expect(result).toContain('End');
    });

    it('preserves code blocks', () => {
      const input = "```javascript\nconst x = 1;\n```";
      const result = parseMarkdown(input);

      expect(result).toContain('<pre');
      expect(result).toContain('<code');
      expect(result).toContain('const x = 1;');
    });

    it('handles lists', () => {
      const input = "- Item 1\n- Item 2\n- Item 3";
      const result = parseMarkdown(input);

      expect(result).toContain('<ul');
      expect(result).toContain('<li');
    });

    it('handles links', () => {
      const input = "[Link text](https://example.com)";
      const result = parseMarkdown(input);

      expect(result).toContain('<a');
      expect(result).toContain('https://example.com');
      expect(result).toContain('Link text');
    });

    it('handles inline code', () => {
      const input = "This is `inline code` example.";
      const result = parseMarkdown(input);

      expect(result).toContain('<code');
      expect(result).toContain('inline code');
    });

    it('handles blockquotes', () => {
      const input = "> This is a quote\n> Multiple lines";
      const result = parseMarkdown(input);

      expect(result).toContain('<blockquote');
    });

    it('handles tables', () => {
      const input = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1   | Cell 2   |";
      const result = parseMarkdown(input);

      expect(result).toContain('<table');
      expect(result).toContain('<th');
      expect(result).toContain('<td');
    });

    it('falls back to plain text for malformed markdown', () => {
      const input = "Just plain text without markdown";
      const result = parseMarkdown(input);

      expect(result).toContain('Just plain text');
    });

    it('handles strikethrough text', () => {
      const input = "This is ~~strikethrough~~ text.";
      const result = parseMarkdown(input);

      expect(result).toContain('<del');
      expect(result).toContain('strikethrough');
    });

    it('preserves line breaks with breaks option', () => {
      const input = "Line 1\nLine 2\nLine 3";
      const result = parseMarkdown(input);

      expect(result).toContain('<br');
    });
  });

  describe('streamText', () => {
    it('streams text in chunks', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "First sentence. Second sentence. Third sentence.";
      await streamText(input, mockContainer, 10);

      expect(mockContainer.appendChild).toHaveBeenCalled();
    });

    it('handles paragraph-based chunking', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph.";
      await streamText(input, mockContainer, 5);

      // Should chunk by paragraphs when multiple paragraphs exist
      expect(mockContainer.appendChild).toHaveBeenCalled();
    });

    it('handles single paragraph with sentence chunking', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "This is a single paragraph with multiple sentences. Here's another one. And a third.";
      await streamText(input, mockContainer, 5);

      expect(mockContainer.appendChild).toHaveBeenCalled();
    });

    it('removes thinking tags from streaming content', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "Normal text<think>Hidden thinking</think>Visible text";
      await streamText(input, mockContainer, 10);

      expect(mockContainer.innerHTML).not.toContain('<think>');
      expect(mockContainer.innerHTML).not.toContain('Hidden thinking');
    });

    it('handles empty streaming content', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const result = await streamText("", mockContainer, 10);

      expect(result).toBeDefined();
    });

    it('handles content with only thinking tags', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "<think>Only thinking content</think>";
      await streamText(input, mockContainer, 10);

      expect(mockContainer.innerHTML).not.toContain('<think>');
    });

    it('respects chunk delay parameter', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const startTime = Date.now();
      const input = "Sentence 1. Sentence 2. Sentence 3.";
      await streamText(input, mockContainer, 50); // 50ms delay
      const endTime = Date.now();

      // Should take at least some time due to delays
      expect(endTime - startTime).toBeGreaterThan(100);
    });

    it('handles markdown in chunks', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "# Heading\n\nThis is **bold** text.";
      await streamText(input, mockContainer, 10);

      expect(mockContainer.innerHTML).toContain('<h1');
      expect(mockContainer.innerHTML).toContain('<strong');
    });

    it('handles code blocks in streaming', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "```python\nprint('hello')\n```";
      await streamText(input, mockContainer, 10);

      expect(mockContainer.innerHTML).toContain('<pre');
      expect(mockContainer.innerHTML).toContain('<code');
    });

    it('handles malformed sentences gracefully', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "No punctuation here Another sentence No periods";
      await streamText(input, mockContainer, 10);

      expect(mockContainer.appendChild).toHaveBeenCalled();
    });

    it('filters out empty chunks', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "Valid sentence.\n\n.\n\nAnother valid sentence.";
      await streamText(input, mockContainer, 10);

      // Should not attempt to stream empty chunks
      expect(mockContainer.appendChild).toHaveBeenCalled();
    });
  });

  describe('configureMarked', () => {
    it('configures marked with correct options', () => {
      const markedSetOptionsSpy = jest.spyOn(marked, 'setOptions');
      
      configureMarked();

      expect(markedSetOptionsSpy).toHaveBeenCalledWith({
        breaks: true,
        gfm: true,
      });

      markedSetOptionsSpy.mockRestore();
    });
  });

  describe('Edge Cases', () => {
    it('handles null input gracefully', () => {
      expect(() => parseMarkdown(null as any)).not.toThrow();
      expect(parseMarkdown(null as any)).toBe("");
    });

    it('handles undefined input gracefully', () => {
      expect(() => parseMarkdown(undefined as any)).not.toThrow();
      expect(parseMarkdown(undefined as any)).toBe("");
    });

    it('handles very long content', () => {
      const longContent = "A".repeat(10000);
      const result = parseMarkdown(longContent);

      expect(result).toContain('A'.repeat(10000));
    });

    it('handles special characters in markdown', () => {
      const input = "Text with & < > \" ' characters";
      const result = parseMarkdown(input);

      expect(result).toContain('Text with');
    });

    it('handles nested markdown structures', () => {
      const input = "> Quote with **bold** and `code`";
      const result = parseMarkdown(input);

      expect(result).toContain('<blockquote');
      expect(result).toContain('<strong');
      expect(result).toContain('<code');
    });

    it('handles streaming with complex markdown', async () => {
      const mockContainer = {
        appendChild: jest.fn(),
        innerHTML: '',
      } as any;

      const input = "# Title\n\n> Quote with **bold**\n\n```js\nconsole.log('test');\n```";
      await streamText(input, mockContainer, 10);

      expect(mockContainer.innerHTML).toContain('<h1');
      expect(mockContainer.innerHTML).toContain('<blockquote');
      expect(mockContainer.innerHTML).toContain('<strong');
      expect(mockContainer.innerHTML).toContain('<pre');
    });
  });
});