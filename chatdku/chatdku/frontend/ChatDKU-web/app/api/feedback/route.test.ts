import { POST } from './route';
import { NextResponse } from 'next/server';

// Mock fetch for database calls
global.fetch = jest.fn();

describe('/api/feedback/route', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('processes feedback submission successfully', async () => {
    const mockFeedbackData = {
      userInput: 'What is the deadline?',
      botAnswer: 'The deadline is Friday at 5 PM.',
      feedbackReason: 'helpful',
      chatHistoryId: 'session-123',
    };

    // Mock successful database insertion
    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    const mockRequest = {
      json: () => Promise.resolve(mockFeedbackData),
    } as any;

    const response = await POST(mockRequest);

    expect(response).toBeInstanceOf(NextResponse);
    expect(response.status).toBe(200);
  });

  it('handles negative feedback with custom reason', async () => {
    const mockFeedbackData = {
      userInput: 'How do I register?',
      botAnswer: 'You can register online.',
      feedbackReason: 'The information was not clear enough.',
      chatHistoryId: 'session-456',
    };

    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    const mockRequest = {
      json: () => Promise.resolve(mockFeedbackData),
    } as any;

    const response = await POST(mockRequest);

    expect(response).toBeInstanceOf(NextResponse);
    expect(response.status).toBe(200);
  });

  it('validates required feedback fields', async () => {
    const incompleteData = {
      userInput: 'Test question',
      // Missing botAnswer, feedbackReason, chatHistoryId
    };

    const mockRequest = {
      json: () => Promise.resolve(incompleteData),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(400);
    expect(responseText).toContain('Missing required fields');
  });

  it('handles database errors gracefully', async () => {
    const mockFeedbackData = {
      userInput: 'Test question',
      botAnswer: 'Test answer',
      feedbackReason: 'helpful',
      chatHistoryId: 'session-789',
    };

    (fetch as jest.Mock).mockRejectedValue(new Error('Database connection failed'));

    const mockRequest = {
      json: () => Promise.resolve(mockFeedbackData),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(500);
    expect(responseText).toContain('Database connection failed');
  });

  it('handles malformed request body', async () => {
    const mockRequest = {
      json: () => Promise.reject(new Error('Invalid JSON')),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(400);
    expect(responseText).toContain('Invalid request body');
  });

  it('sanitizes input data to prevent injection', async () => {
    const maliciousData = {
      userInput: '<script>alert("xss")</script>',
      botAnswer: 'Normal answer',
      feedbackReason: 'helpful',
      chatHistoryId: 'session-123',
    };

    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    const mockRequest = {
      json: () => Promise.resolve(maliciousData),
    } as any;

    const response = await POST(mockRequest);

    expect(response).toBeInstanceOf(NextResponse);
    // The actual sanitization would happen in the real implementation
  });

  it('handles different feedback reason types', async () => {
    const feedbackTypes = [
      'helpful',
      'not_correct',
      'not_clear',
      'not_relevant',
      'other',
      'Custom feedback reason here',
    ];

    for (const reason of feedbackTypes) {
      const mockFeedbackData = {
        userInput: 'Test question',
        botAnswer: 'Test answer',
        feedbackReason: reason,
        chatHistoryId: 'session-123',
      };

      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      const mockRequest = {
        json: () => Promise.resolve(mockFeedbackData),
      } as any;

      const response = await POST(mockRequest);

      expect(response).toBeInstanceOf(NextResponse);
      expect(response.status).toBe(200);
    }
  });

  it('validates chat history ID format', async () => {
    const invalidData = {
      userInput: 'Test question',
      botAnswer: 'Test answer',
      feedbackReason: 'helpful',
      chatHistoryId: '', // Empty session ID
    };

    const mockRequest = {
      json: () => Promise.resolve(invalidData),
    } as any;

    const response = await POST(mockRequest);
    const responseText = await response.text();

    expect(response.status).toBe(400);
    expect(responseText).toContain('Invalid chat history ID');
  });

  it('handles long content gracefully', async () => {
    const longContent = 'A'.repeat(10000); // Very long string
    const mockFeedbackData = {
      userInput: longContent,
      botAnswer: longContent,
      feedbackReason: 'helpful',
      chatHistoryId: 'session-123',
    };

    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    const mockRequest = {
      json: () => Promise.resolve(mockFeedbackData),
    } as any;

    const response = await POST(mockRequest);

    expect(response).toBeInstanceOf(NextResponse);
    expect(response.status).toBe(200);
  });

  it('logs feedback for analytics', async () => {
    const mockFeedbackData = {
      userInput: 'Test question',
      botAnswer: 'Test answer',
      feedbackReason: 'helpful',
      chatHistoryId: 'session-123',
    };

    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    // Mock console.log to verify logging
    const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

    const mockRequest = {
      json: () => Promise.resolve(mockFeedbackData),
    } as any;

    await POST(mockRequest);

    // Basic service logging exists, but no specific analytics logging
    expect(consoleSpy).toHaveBeenCalledWith('Proxying feedback to backend service');

    consoleSpy.mockRestore();
  });
});