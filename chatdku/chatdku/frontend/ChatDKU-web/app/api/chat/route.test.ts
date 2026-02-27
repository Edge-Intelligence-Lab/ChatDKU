import { POST } from './route';
import { NextResponse } from 'next/server';

// Mock fetch for backend calls
global.fetch = jest.fn();

describe('/api/chat/route', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('proxies chat requests to backend successfully', async () => {
    const mockRequestBody = {
      messages: [{ role: 'user', content: 'Hello' }],
      chatHistoryId: 'test-session',
    };

    const mockBackendResponse = 'Backend response';
    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(mockBackendResponse),
    });

    const mockRequest = {
      json: () => Promise.resolve(mockRequestBody),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:9015/chat',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mockRequestBody),
      })
    );

    expect(response).toBeInstanceOf(NextResponse);
    expect(responseText).toBe(mockBackendResponse);
  });

  it('handles backend errors gracefully', async () => {
    const mockRequestBody = {
      messages: [{ role: 'user', content: 'Hello' }],
    };

    (fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    const mockRequest = {
      json: () => Promise.resolve(mockRequestBody),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(500);
    expect(responseText).toContain('Backend error: Internal Server Error');
  });

  it('handles network errors', async () => {
    const mockRequestBody = {
      messages: [{ role: 'user', content: 'Hello' }],
    };

    (fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

    const mockRequest = {
      json: () => Promise.resolve(mockRequestBody),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(500);
    expect(responseText).toContain('Error: Network error');
  });

  it('handles malformed request body', async () => {
    const mockRequest = {
      json: () => Promise.reject(new Error('Invalid JSON')),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(500);
    expect(responseText).toContain('Error: Invalid JSON');
  });

  it('passes through request body unchanged', async () => {
    const complexRequestBody = {
      messages: [
        { role: 'user', content: 'Hello' },
        { role: 'assistant', content: 'Hi there!' },
      ],
      chatHistoryId: 'session-123',
      mode: 'agent',
      searchMode: 'document',
      metadata: {
        timestamp: '2024-01-01T00:00:00Z',
        userId: 'user-456',
      },
    };

    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('Response'),
    });

    const mockRequest = {
      json: () => Promise.resolve(complexRequestBody),
    } as any;

    await POST(mockRequest);

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:9015/chat',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(complexRequestBody),
      })
    );
  });

  it('maintains request headers and method', async () => {
    const mockRequestBody = { test: 'data' };

    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('Success'),
    });

    const mockRequest = {
      json: () => Promise.resolve(mockRequestBody),
    } as any;

    await POST(mockRequest);

    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
  });

  it('handles empty request body', async () => {
    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('Empty response'),
    });

    const mockRequest = {
      json: () => Promise.resolve({}),
    } as any;

    const response = await POST(mockRequest);

    expect(response).toBeInstanceOf(NextResponse);
    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: '{}',
      })
    );
  });

  it('preserves response content type', async () => {
    const mockResponse = 'Plain text response';
    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(mockResponse),
    });

    const mockRequest = {
      json: () => Promise.resolve({ test: 'data' }),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(responseText).toBe(mockResponse);
  });

  it('handles backend timeout', async () => {
    (fetch as jest.Mock).mockRejectedValue(new Error('ETIMEDOUT'));

    const mockRequest = {
      json: () => Promise.resolve({ test: 'data' }),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(500);
    expect(responseText).toContain('Error: ETIMEDOUT');
  });
});
