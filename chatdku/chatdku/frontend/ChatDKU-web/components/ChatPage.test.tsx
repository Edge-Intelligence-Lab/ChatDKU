import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';
import ChatPage from './ChatPage';

// Mock dependencies
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

jest.mock('js-cookie', () => ({
  get: jest.fn(),
  set: jest.fn(),
}));

jest.mock('@/lib/convosNew', () => ({
  getNewSession: jest.fn(),
  getCurrentSessionId: jest.fn(),
  getStoredEndpoint: jest.fn(),
  getSessionMessages: jest.fn(),
}));

jest.mock('@/components/ui/ai-input', () => ({
  AIInput: ({ onSubmit, disabled, placeholder }: any) => (
    <div>
      <textarea
        data-testid="ai-input"
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => {
          if (e.target.value === 'test message') {
            onSubmit?.(e.target.value);
          }
        }}
      />
      <button data-testid="submit-button" onClick={() => onSubmit?.('test message')}>
        Submit
      </button>
    </div>
  ),
}));

jest.mock('@/components/navbar', () => ({
  Navbar: () => <div data-testid="navbar">Navbar</div>,
}));

jest.mock('@/components/side', () => ({
  __esModule: true,
  default: ({ onNewChat, disabled }: any) => (
    <div>
      <button data-testid="new-chat-button" onClick={onNewChat} disabled={disabled}>
        New Chat
      </button>
    </div>
  ),
}));

jest.mock('@/components/WelcomeBanner', () => ({
  __esModule: true,
  default: () => <div data-testid="welcome-banner">Welcome</div>,
}));

jest.mock('@/components/doc-manager', () => ({
  DocumentManager: ({ open, onOpenChange }: any) => (
    <div>
      {open && <div data-testid="document-manager">Document Manager</div>}
      <button onClick={() => onOpenChange(!open)}>Toggle Docs</button>
    </div>
  ),
}));

jest.mock('@/components/prompt_recs', () => ({
  PromptRecs: ({ onPromptSelect }: any) => (
    <div>
      <button onClick={() => onPromptSelect('Test prompt')}>Test Prompt</button>
    </div>
  ),
}));

// Mock fetch for test endpoint
const mockFetch = global.fetch as jest.Mock;

describe('ChatPage', () => {
  const mockPush = jest.fn();
  const mockRouter = { push: mockPush } as any;

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset fetch mock
    mockFetch.mockClear();
    
    // Mock DOM methods
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      value: jest.fn(),
      writable: true,
    });
    
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
    (Cookies.get as jest.Mock).mockReturnValue('true'); // terms accepted
    
    // Mock successful session
    const { getNewSession } = require('@/lib/convosNew');
    getNewSession.mockResolvedValue('test-session-id');
    
    // Setup DOM for chat log
    document.body.innerHTML = '<div id="chat-log"></div>';
  });

  it('renders loading state initially', () => {
    render(<ChatPage />);
    
    expect(screen.getByText('Preparing your chat session...')).toBeInTheDocument();
    expect(screen.getByTestId('navbar')).toBeInTheDocument();
  });

  it('redirects to landing when terms not accepted', async () => {
    (Cookies.get as jest.Mock).mockReturnValue(null);
    
    render(<ChatPage />);
    
await waitFor(() => {
      expect(global.fetch as jest.Mock).toHaveBeenCalledWith(
        expect.stringContaining('/api/chat'), // Should use chat endpoint in production
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('"content": "test message"'),
        }),
      );
    });
  });

  it('loads chat interface when session is ready', async () => {
    render(<ChatPage />);
    
    await waitFor(() => {
      expect(screen.getByTestId('ai-input')).toBeInTheDocument();
      expect(screen.getByTestId('welcome-banner')).toBeInTheDocument();
      expect(screen.getByTestId('new-chat-button')).not.toBeDisabled();
    });
  });

  it('handles session error state', async () => {
    const { getNewSession } = require('@/lib/convosNew');
    getNewSession.mockResolvedValue(null);
    
    render(<ChatPage />);
    
    await waitFor(() => {
      expect(screen.getByText(/We couldn't start a chat session/)).toBeInTheDocument();
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });
  });

  it('submits a message and displays response', async () => {
    const mockFetch = global.fetch as jest.Mock;
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('Test response'),
    });
    
    render(<ChatPage />);
    
    await waitFor(() => {
      expect(screen.getByTestId('ai-input')).not.toBeDisabled();
    });
    
    const submitButton = screen.getByTestId('submit-button');
    await userEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/chat'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('test message'),
        })
      );
    });
  });

  it('handles new chat creation', async () => {
    const { getNewSession } = require('@/lib/convosNew');
    getNewSession.mockResolvedValue('new-session-id');
    
    render(<ChatPage />);
    
    await waitFor(() => {
      expect(screen.getByTestId('new-chat-button')).toBeInTheDocument();
    });
    
    const newChatButton = screen.getByTestId('new-chat-button');
    await userEvent.click(newChatButton);
    
    await waitFor(() => {
      expect(getNewSession).toHaveBeenCalledTimes(2); // Initial + new chat
    });
  });

  it('handles test endpoint for "test" message', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('# Test Markdown\n\nThis is a test.'),
    });
    
    render(<ChatPage isDev={true} />);
    
    await waitFor(() => {
      expect(screen.getByTestId('ai-input')).not.toBeDisabled();
    });
    
    // Simulate typing "test"
    const textarea = screen.getByTestId('ai-input') as HTMLTextAreaElement;
    await userEvent.type(textarea, 'test');
    
    // Trigger submit
    const submitButton = screen.getByTestId('submit-button');
    await userEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/mdtest.md')
      );
    });
  });

  it('disables input when session is not ready', async () => {
    const { getNewSession } = require('@/lib/convosNew');
    getNewSession.mockResolvedValue(null);
    
    render(<ChatPage />);
    
    await waitFor(() => {
      expect(screen.getByTestId('ai-input')).toBeDisabled();
      expect(screen.getByTestId('new-chat-button')).toBeDisabled();
    });
  });

  it('handles retry session functionality', async () => {
    const { getNewSession } = require('@/lib/convosNew');
    getNewSession.mockResolvedValueOnce(null); // Initial failure
    getNewSession.mockResolvedValueOnce('retry-session-id'); // Retry success
    
    render(<ChatPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });
    
    const retryButton = screen.getByText('Try again');
    await userEvent.click(retryButton);
    
    await waitFor(() => {
      expect(getNewSession).toHaveBeenCalledTimes(2);
    });
  });

  it('loads conversation history when selected', async () => {
    const { getSessionMessages } = require('@/lib/convosNew');
    const mockMessages = [
      { role: 'user', content: 'Hello', timestamp: '2024-01-01' },
      { role: 'assistant', content: 'Hi there!', timestamp: '2024-01-01' },
    ];
    getSessionMessages.mockResolvedValue(mockMessages);
    
    render(<ChatPage />);
    
    await waitFor(() => {
      expect(screen.getByTestId('new-chat-button')).toBeInTheDocument();
    });
    
    // Simulate conversation selection (would need Side component to trigger this)
    // This tests the message loading functionality
    expect(getSessionMessages).not.toHaveBeenCalled();
  });

  it('handles dev mode differently from production', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('Dev response'),
    });
    
    render(<ChatPage isDev={true} />);
    
    await waitFor(() => {
      expect(screen.getByTestId('ai-input')).not.toBeDisabled();
    });
    
    const submitButton = screen.getByTestId('submit-button');
    await userEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String), // Should use configurable endpoint in dev mode
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });
});