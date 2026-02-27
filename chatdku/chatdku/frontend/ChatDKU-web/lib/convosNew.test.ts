import {
  getNewSession,
  getCurrentSessionId,
  setCurrentSessionId,
  clearSessionId,
  getSessionMessages,
  getConversations,
  getStoredEndpoint,
  setStoredEndpoint,
  clearStoredEndpoint,
} from './convosNew';

// Mock fetch
global.fetch = jest.fn();

// Mock document.cookie
Object.defineProperty(document, 'cookie', {
  writable: true,
  value: '',
});

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};
global.localStorage = localStorageMock;

// Ensure window is defined for client-side tests
if (!global.window) {
  (global as any).window = {};
}

// Mock localStorage on window
Object.defineProperty(global.window, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

describe('convosNew', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    document.cookie = '';
    localStorageMock.getItem.mockClear();
    localStorageMock.setItem.mockClear();
    localStorageMock.removeItem.mockClear();
  });

  describe('Session Management', () => {
    describe('getNewSession', () => {
      it('creates a new session successfully', async () => {
        const mockResponse = { session_id: 'new-session-123' };
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockResponse),
        });

        const result = await getNewSession();

        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/get_session'),
          expect.objectContaining({
            method: 'GET',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
          })
        );
        expect(result).toBe('new-session-123');
        expect(document.cookie).toContain('chatdku_session_id=new-session-123');
      });

      it('handles session creation failure', async () => {
        (fetch as jest.Mock).mockResolvedValue({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
        });

        const result = await getNewSession();

        expect(result).toBeNull();
        expect(document.cookie).not.toContain('chatdku_session_id');
      });

      it('handles network errors', async () => {
        (fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

        const result = await getNewSession();

        expect(result).toBeNull();
      });

      it('handles empty session_id response', async () => {
        const mockResponse = { session_id: '' };
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockResponse),
        });

        const result = await getNewSession();

        expect(result).toBe('');
        expect(document.cookie).toContain('chatdku_session_id=');
      });
    });

    describe('getCurrentSessionId', () => {
      it('retrieves session ID from cookies', () => {
        document.cookie = 'chatdku_session_id=test-session-456; other=value';
        const result = getCurrentSessionId();

        expect(result).toBe('test-session-456');
      });

      it('returns null when no session cookie exists', () => {
        document.cookie = 'other=value';
        const result = getCurrentSessionId();

        expect(result).toBeNull();
      });

      it('returns null in server environment', () => {
        const originalWindow = global.window;
        delete (global as any).window;

        const result = getCurrentSessionId();

        expect(result).toBeNull();

        global.window = originalWindow;
      });

      it('handles URL-encoded session IDs', () => {
        document.cookie = 'chatdku_session_id=session%20with%20spaces';
        const result = getCurrentSessionId();

        expect(result).toBe('session with spaces');
      });
    });

    describe('setCurrentSessionId', () => {
      it('sets session ID in cookies', () => {
        setCurrentSessionId('new-session-789');

        expect(document.cookie).toContain('chatdku_session_id=new-session-789');
      });

      it('does nothing in server environment', () => {
        const originalWindow = global.window;
        const originalDocument = global.document;
        delete (global as any).window;
        delete (global as any).document;

        // Clear any existing cookies
        if (originalDocument) {
          originalDocument.cookie = '';
        }

        setCurrentSessionId('should-not-set');

        console.log('document after call:', typeof document, document.cookie);
        expect(document.cookie).not.toContain('should-not-set');

        global.window = originalWindow;
        global.document = originalDocument;
      });
    });

    describe('clearSessionId', () => {
      it('clears session ID from cookies', () => {
        document.cookie = 'chatdku_session_id=test-session; other=value';
        clearSessionId();

        expect(document.cookie).toContain('chatdku_session_id=;');
        expect(document.cookie).toContain('expires=Thu, 01 Jan 1970 00:00:00 GMT');
      });

      it('does nothing in server environment', () => {
        const originalWindow = global.window;
        delete (global as any).window;

        clearSessionId();

        global.window = originalWindow;
      });
    });
  });

  describe('Message Management', () => {
    describe('getSessionMessages', () => {
      it('retrieves messages successfully', async () => {
        const mockMessages = [
          { role: 'user', content: 'Hello', timestamp: '2024-01-01T00:00:00Z' },
          { role: 'bot', content: 'Hi there!', timestamp: '2024-01-01T00:00:01Z' },
        ];
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockMessages),
        });

        const result = await getSessionMessages('test-session-id');

        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/c/test-session-id/messages'),
          expect.objectContaining({
            method: 'GET',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
          })
        );
        expect(result).toHaveLength(2);
        expect(result[0]).toEqual({
          role: 'user',
          content: 'Hello',
          timestamp: '2024-01-01T00:00:00Z',
        });
        expect(result[1]).toEqual({
          role: 'assistant',
          content: 'Hi there!',
          timestamp: '2024-01-01T00:00:01Z',
        });
      });

      it('handles different role formats', async () => {
        const mockMessages = [
          { role: 'User', content: 'Hello' },
          { role: 'Bot', content: 'Hi' },
          { role: 'assistant', content: 'Hey' },
          { role: 'user', content: 'Hey back' },
        ];
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockMessages),
        });

        const result = await getSessionMessages('test-session');

        expect(result[0].role).toBe('user');
        expect(result[1].role).toBe('assistant');
        expect(result[2].role).toBe('assistant');
        expect(result[3].role).toBe('user');
      });

      it('handles array content in messages', async () => {
        const mockMessages = [
          {
            role: 'assistant',
            content: [
              { type: 'text', text: 'Part 1' },
              { type: 'text', text: 'Part 2' },
            ],
          },
        ];
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockMessages),
        });

        const result = await getSessionMessages('test-session');

        expect(result[0].content).toBe('Part 1\nPart 2');
      });

      it('handles object content in messages', async () => {
        const mockMessages = [
          {
            role: 'assistant',
            content: { text: 'Object content' },
          },
        ];
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockMessages),
        });

        const result = await getSessionMessages('test-session');

        expect(result[0].content).toBe('Object content');
      });

      it('falls back to message field when content is missing', async () => {
        const mockMessages = [
          {
            role: 'user',
            message: 'Fallback message',
          },
        ];
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockMessages),
        });

        const result = await getSessionMessages('test-session');

        expect(result[0].content).toBe('Fallback message');
      });

      it('handles API errors', async () => {
        (fetch as jest.Mock).mockResolvedValue({
          ok: false,
          status: 404,
          statusText: 'Not Found',
        });

        const result = await getSessionMessages('invalid-session');

        expect(result).toEqual([]);
      });

      it('handles network errors', async () => {
        (fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

        const result = await getSessionMessages('test-session');

        expect(result).toEqual([]);
      });
    });

    describe('getConversations', () => {
      it('retrieves conversations list successfully', async () => {
        const mockConversations = [
          { id: 'conv1', title: 'Chat 1', created_at: '2024-01-01T00:00:00Z' },
          { id: 'conv2', created_at: '2024-01-02T00:00:00Z' }, // No title
        ];
        (fetch as jest.Mock).mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockConversations),
        });

        const result = await getConversations();

        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/c/'),
          expect.objectContaining({
            method: 'GET',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
          })
        );
        expect(result).toHaveLength(2);
        expect(result[0]).toEqual({
          id: 'conv1',
          title: 'Chat 1',
          created_at: new Date('2024-01-01T00:00:00Z'),
        });
        expect(result[1]).toEqual({
          id: 'conv2',
          title: 'New Chat', // Fallback title
          created_at: new Date('2024-01-02T00:00:00Z'),
        });
      });

      it('handles API errors', async () => {
        (fetch as jest.Mock).mockResolvedValue({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
        });

        const result = await getConversations();

        expect(result).toEqual([]);
      });

      it('handles network errors', async () => {
        (fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

        const result = await getConversations();

        expect(result).toEqual([]);
      });
    });
  });

  describe('Endpoint Management', () => {
    describe('getStoredEndpoint', () => {
      it('retrieves endpoint from localStorage', () => {
        localStorageMock.getItem.mockReturnValue('https://custom-endpoint.com');
        const result = getStoredEndpoint();

        expect(result).toBe('https://custom-endpoint.com');
        expect(localStorageMock.getItem).toHaveBeenCalledWith('chatdku_api_endpoint');
      });

      it('returns default endpoint when none stored', () => {
        localStorageMock.getItem.mockReturnValue(null);
        const result = getStoredEndpoint();

        expect(result).toBe('http://localhost:3005/api/chat');
      });

      it('returns default endpoint in server environment', () => {
        const originalWindow = global.window;
        delete (global as any).window;

        const result = getStoredEndpoint();

        expect(result).toBe('http://localhost:3005/api/chat');

        global.window = originalWindow;
      });
    });

    describe('setStoredEndpoint', () => {
      it('stores endpoint in localStorage', () => {
        setStoredEndpoint('https://new-endpoint.com');

        expect(localStorageMock.setItem).toHaveBeenCalledWith(
          'chatdku_api_endpoint',
          'https://new-endpoint.com'
        );
      });

      it('does nothing in server environment', () => {
        const originalWindow = global.window;
        const originalLocalStorage = global.localStorage;
        
        (global as any).window = undefined;
        (global as any).localStorage = undefined;

        setStoredEndpoint('https://should-not-store.com');

        expect(localStorageMock.setItem).not.toHaveBeenCalled();

        global.window = originalWindow;
        global.localStorage = originalLocalStorage;
      });
    });

    describe('clearStoredEndpoint', () => {
      it('removes endpoint from localStorage', () => {
        clearStoredEndpoint();

        expect(localStorageMock.removeItem).toHaveBeenCalledWith('chatdku_api_endpoint');
      });

      it('does nothing in server environment', () => {
        const originalWindow = global.window;
        const originalLocalStorage = global.localStorage;
        
        (global as any).window = undefined;
        (global as any).localStorage = undefined;

        clearStoredEndpoint();

        expect(localStorageMock.removeItem).not.toHaveBeenCalled();

        global.window = originalWindow;
        global.localStorage = originalLocalStorage;
      });
    });
  });

  describe('Cookie Utilities', () => {
    it('handles special characters in session IDs', () => {
      setCurrentSessionId('session+with=special&chars');
      expect(document.cookie).toContain('chatdku_session_id=session%2Bwith%3Dspecial%26chars');
    });

    it('handles multiple cookies', () => {
      document.cookie = 'other=value; path=/';
      setCurrentSessionId('test-session');
      expect(document.cookie).toContain('chatdku_session_id=test-session');
      expect(document.cookie).toContain('other=value');
    });

    it('properly decodes URL-encoded cookies', () => {
      document.cookie = 'chatdku_session_id=session%20with%20spaces';
      const result = getCurrentSessionId();
      expect(result).toBe('session with spaces');
    });
  });

  describe('Error Handling', () => {
    it('handles malformed JSON responses', async () => {
      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.reject(new Error('Unexpected token in JSON')),
      });

      const result = await getNewSession();

      expect(result).toBeNull();
    });

    it('handles missing session_id in response', async () => {
      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}), // Empty response
      });

      const result = await getNewSession();

      expect(result).toBeUndefined();
    });

    it('handles invalid date strings in conversations', async () => {
      const mockConversations = [
        { id: 'conv1', title: 'Chat 1', created_at: 'invalid-date' },
      ];
      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockConversations),
      });

      const result = await getConversations();

      expect(result[0].created_at).toBeInstanceOf(Date);
      expect(isNaN(result[0].created_at.getTime())).toBe(true);
    });
  });
});
