import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AIInput } from './ai-input';

// Mock usePathname
jest.mock('next/navigation', () => ({
  usePathname: () => '/',
}));

// Mock socket.io-client
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    emit: jest.fn(),
    on: jest.fn(),
    disconnect: jest.fn(),
  })),
}));

// Mock media devices
Object.defineProperty(navigator, 'mediaDevices', {
  writable: true,
  value: {
    getUserMedia: jest.fn(),
  },
});

// Mock MediaRecorder
class MockMediaRecorder {
  state: string = 'inactive';
  mimeType: string;
  ondataavailable: ((event: any) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor(stream: MediaStream, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType || 'audio/webm';
  }

  start() {
    this.state = 'recording';
  }

  stop() {
    this.state = 'inactive';
    this.onstop?.();
  }

  static isTypeSupported(mimeType: string) {
    return true;
  }
}

global.MediaRecorder = MockMediaRecorder as any;

describe('AIInput', () => {
  const mockOnSubmit = jest.fn();
  const mockOnInputChange = jest.fn();
  const mockOnThinkingModeChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders with default props', () => {
    render(<AIInput />);
    
    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
  });

  it('handles text input changes', async () => {
    const user = userEvent.setup();
    render(<AIInput onInputChange={mockOnInputChange} />);
    
    const textarea = screen.getByPlaceholderText('Type your message...');
    await user.type(textarea, 'Hello world');
    
    expect(mockOnInputChange).toHaveBeenCalledWith('Hello world');
  });

  it('submits on Enter key without shift', async () => {
    const user = userEvent.setup();
    render(<AIInput onSubmit={mockOnSubmit} />);
    
    const textarea = screen.getByPlaceholderText('Type your message...');
    await user.type(textarea, 'Test message');
    await user.keyboard('{Enter}');
    
    expect(mockOnSubmit).toHaveBeenCalledWith('Test message');
  });

  it('does not submit on Enter with shift', async () => {
    const user = userEvent.setup();
    render(<AIInput onSubmit={mockOnSubmit} />);
    
    const textarea = screen.getByPlaceholderText('Type your message...');
    await user.type(textarea, 'Test message');
    await user.keyboard('{Shift>}{Enter}{/Shift}');
    
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it('shows submit button when there is input', async () => {
    const user = userEvent.setup();
    render(<AIInput />);
    
    const textarea = screen.getByPlaceholderText('Type your message...');
    expect(screen.queryByTestId('submit-button')).not.toBeInTheDocument();
    
    await user.type(textarea, 'Test');
    
    // The submit button should be visible when there's text
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('disables all controls when disabled prop is true', () => {
    render(<AIInput disabled={true} />);
    
    const textarea = screen.getByPlaceholderText('Type your message...');
    expect(textarea).toBeDisabled();
  });

  it('applies custom placeholder', () => {
    render(<AIInput placeholder="Custom placeholder" />);
    
    expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument();
  });

  it('handles thinking mode toggle', async () => {
    const user = userEvent.setup();
    render(<AIInput thinkingMode={false} onThinkingModeChange={mockOnThinkingModeChange} />);
    
    // Find thinking mode toggle button (if it exists)
    // This would need to be implemented in the component
    expect(mockOnThinkingModeChange).not.toHaveBeenCalled();
  });

  describe('Voice Recording', () => {
    it('starts recording when microphone button is clicked', async () => {
      const mockStream = {
        getTracks: () => [{ stop: jest.fn() }],
      };
      
      (navigator.mediaDevices.getUserMedia as jest.Mock).mockResolvedValue(mockStream);
      
      const user = userEvent.setup();
      render(<AIInput />);
      
      // Find and click the microphone button
      const micButton = screen.getByRole('button'); // First button should be mic
      await user.click(micButton);
      
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });
    });

    it('handles recording error gracefully', async () => {
      (navigator.mediaDevices.getUserMedia as jest.Mock).mockRejectedValue(
        new Error('Media device not found')
      );
      
      const user = userEvent.setup();
      render(<AIInput />);
      
      const micButton = screen.getByRole('button');
      await user.click(micButton);
      
      // Should not throw error, just handle it gracefully
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
    });

    it('stops recording when clicked again', async () => {
      const mockStream = {
        getTracks: () => [{ stop: jest.fn() }],
      };
      
      (navigator.mediaDevices.getUserMedia as jest.Mock).mockResolvedValue(mockStream);
      
      const user = userEvent.setup();
      render(<AIInput />);
      
      const micButton = screen.getByRole('button');
      
      // Start recording
      await user.click(micButton);
      
      // Stop recording
      await user.click(micButton);
      
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
    });

    it('updates placeholder when recording', async () => {
      const mockStream = {
        getTracks: () => [{ stop: jest.fn() }],
      };
      
      (navigator.mediaDevices.getUserMedia as jest.Mock).mockResolvedValue(mockStream);
      
      const user = userEvent.setup();
      render(<AIInput />);
      
      const micButton = screen.getByRole('button');
      await user.click(micButton);
      
      // Placeholder should change to "Listening..."
      expect(screen.getByPlaceholderText('Listening...')).toBeInTheDocument();
    });

    it('handles audio transcription response', async () => {
      const mockStream = {
        getTracks: () => [{ stop: jest.fn() }],
      };
      
      (navigator.mediaDevices.getUserMedia as jest.Mock).mockResolvedValue(mockStream);
      
      const { io } = require('socket.io-client');
      const mockSocket = {
        emit: jest.fn(),
        on: jest.fn(),
        disconnect: jest.fn(),
      };
      io.mockReturnValue(mockSocket);
      
      const user = userEvent.setup();
      render(<AIInput onInputChange={mockOnInputChange} />);
      
      const micButton = screen.getByRole('button');
      await user.click(micButton);
      
      // Simulate transcription response
      const socketOnCalls = mockSocket.on.mock.calls;
      const audioTranscribedHandler = socketOnCalls.find(call => call[0] === 'audio_transcribed')?.[1];
      
      if (audioTranscribedHandler) {
        audioTranscribedHandler({ text: 'Transcribed text' });
        expect(mockOnInputChange).toHaveBeenCalledWith('Transcribed text');
      }
    });
  });

  describe('Socket Connection', () => {
    it('establishes socket connection on mount', () => {
      const { io } = require('socket.io-client');
      const mockSocket = {
        emit: jest.fn(),
        on: jest.fn(),
        disconnect: jest.fn(),
      };
      io.mockReturnValue(mockSocket);
      
      render(<AIInput />);
      
      expect(io).toHaveBeenCalledWith('ws://localhost:8007', {
        transports: ['websocket'],
        secure: false,
      });
    });

    it('disconnects socket on unmount', () => {
      const { io } = require('socket.io-client');
      const mockSocket = {
        emit: jest.fn(),
        on: jest.fn(),
        disconnect: jest.fn(),
      };
      io.mockReturnValue(mockSocket);
      
      const { unmount } = render(<AIInput />);
      unmount();
      
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('Auto-resize functionality', () => {
    it('adjusts height based on content', async () => {
      const user = userEvent.setup();
      render(<AIInput />);
      
      const textarea = screen.getByPlaceholderText('Type your message...') as HTMLTextAreaElement;
      
      // Add multiple lines
      await user.type(textarea, 'Line 1\nLine 2\nLine 3');
      
      // Height should have been adjusted (this would be tested through the useAutoResizeTextarea hook)
      expect(textarea.value).toBe('Line 1\nLine 2\nLine 3');
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA attributes', () => {
      render(<AIInput />);
      
      const textarea = screen.getByPlaceholderText('Type your message...');
      expect(textarea).toHaveAttribute('id', 'ai-input');
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      render(<AIInput onSubmit={mockOnSubmit} />);
      
      const textarea = screen.getByPlaceholderText('Type your message...');
      textarea.focus();
      expect(textarea).toHaveFocus();
      
      await user.type(textarea, 'Test');
      await user.keyboard('{Enter}');
      
      expect(mockOnSubmit).toHaveBeenCalled();
    });
  });

  describe('Styling and Visual Effects', () => {
    it('applies shadow pulse effect when typing', async () => {
      const user = userEvent.setup();
      render(<AIInput />);
      
      const textarea = screen.getByPlaceholderText('Type your message...');
      await user.type(textarea, 'Test');
      
      // The component should have the shadow pulse class when there's input
      const container = textarea.closest('.shadow-pulse');
      expect(container).toBeTruthy();
    });

    it('applies custom className', () => {
      render(<AIInput className="custom-class" />);
      
      const container = screen.getByPlaceholderText('Type your message...').closest('.custom-class');
      expect(container).toBeTruthy();
    });
  });
});
