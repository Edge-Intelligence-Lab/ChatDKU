import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the feedback functionality from ChatPage
const createFeedbackComponent = () => {
  const handleFeedback = jest.fn();
  
  const FeedbackComponent = ({ userMessage, botResponse }: any) => {
    const [showDialog, setShowDialog] = React.useState(false);
    const [selectedReason, setSelectedReason] = React.useState('');
    const [customReason, setCustomReason] = React.useState('');
    const [feedbackSubmitted, setFeedbackSubmitted] = React.useState(false);

    const handleYesClick = () => {
      handleFeedback(userMessage, botResponse, 'helpful');
      setFeedbackSubmitted(true);
    };

    const handleNoClick = () => {
      setShowDialog(true);
    };

    const handleReasonSelect = (reason: string) => {
      setSelectedReason(reason);
      if (reason !== 'other') {
        setCustomReason('');
      }
    };

    const handleSubmit = () => {
      if (!selectedReason) return;
      
      const reasonToSend = selectedReason === 'other' ? customReason : selectedReason;
      if (selectedReason === 'other' && !customReason.trim()) {
        return;
      }
      
      handleFeedback(userMessage, botResponse, reasonToSend);
      setShowDialog(false);
      setFeedbackSubmitted(true);
    };

    const handleCancel = () => {
      setShowDialog(false);
      setSelectedReason('');
      setCustomReason('');
    };

    if (feedbackSubmitted) {
      return <span data-testid="feedback-thanks">Thanks for your feedback!</span>;
    }

    return (
      <div data-testid="feedback-component">
        <div className="flex items-center gap-2">
          <span className="text-sm">Was this response helpful?</span>
          <button data-testid="feedback-yes" onClick={handleYesClick}>Yes</button>
          <button data-testid="feedback-no" onClick={handleNoClick}>No</button>
        </div>
        
        {showDialog && (
          <div data-testid="feedback-dialog">
            <h3>Sorry to hear that. Can you tell us why?</h3>
            <div data-testid="reason-options">
              <button 
                data-testid="reason-not-correct" 
                onClick={() => handleReasonSelect('not_correct')}
                className={selectedReason === 'not_correct' ? 'selected' : ''}
              >
                Not Correct
              </button>
              <button 
                data-testid="reason-not-clear" 
                onClick={() => handleReasonSelect('not_clear')}
                className={selectedReason === 'not_clear' ? 'selected' : ''}
              >
                Not Clear
              </button>
              <button 
                data-testid="reason-not-relevant" 
                onClick={() => handleReasonSelect('not_relevant')}
                className={selectedReason === 'not_relevant' ? 'selected' : ''}
              >
                Not Relevant
              </button>
              <button 
                data-testid="reason-other" 
                onClick={() => handleReasonSelect('other')}
                className={selectedReason === 'other' ? 'selected' : ''}
              >
                Other
              </button>
            </div>
            
            {selectedReason === 'other' && (
              <textarea
                data-testid="custom-reason"
                value={customReason}
                onChange={(e) => setCustomReason(e.target.value)}
                placeholder="Please describe the issue"
                rows={3}
              />
            )}
            
            <div className="flex gap-2">
              <button data-testid="submit-feedback" onClick={handleSubmit}>Submit</button>
              <button data-testid="cancel-feedback" onClick={handleCancel}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    );
  };

  return { FeedbackComponent, handleFeedback };
};

describe('Feedback System', () => {
  const { FeedbackComponent, handleFeedback } = createFeedbackComponent();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders feedback buttons', () => {
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    expect(screen.getByText('Was this response helpful?')).toBeInTheDocument();
    expect(screen.getByTestId('feedback-yes')).toBeInTheDocument();
    expect(screen.getByTestId('feedback-no')).toBeInTheDocument();
  });

  it('handles positive feedback', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test question" botResponse="Test answer" />);
    
    const yesButton = screen.getByTestId('feedback-yes');
    await user.click(yesButton);
    
    expect(handleFeedback).toHaveBeenCalledWith('Test question', 'Test answer', 'helpful');
    expect(screen.getByTestId('feedback-thanks')).toBeInTheDocument();
  });

  it('opens feedback dialog for negative feedback', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    const noButton = screen.getByTestId('feedback-no');
    await user.click(noButton);
    
    expect(screen.getByTestId('feedback-dialog')).toBeInTheDocument();
    expect(screen.getByText('Sorry to hear that. Can you tell us why?')).toBeInTheDocument();
  });

  it('displays all reason options in dialog', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    
    expect(screen.getByTestId('reason-not-correct')).toBeInTheDocument();
    expect(screen.getByTestId('reason-not-clear')).toBeInTheDocument();
    expect(screen.getByTestId('reason-not-relevant')).toBeInTheDocument();
    expect(screen.getByTestId('reason-other')).toBeInTheDocument();
  });

  it('allows selecting predefined reasons', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-not-correct'));
    
    expect(screen.getByTestId('reason-not-correct')).toHaveClass('selected');
  });

  it('shows custom reason textarea when "Other" is selected', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-other'));
    
    expect(screen.getByTestId('custom-reason')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Please describe the issue')).toBeInTheDocument();
  });

  it('submits feedback with predefined reason', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test question" botResponse="Test answer" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-not-clear'));
    await user.click(screen.getByTestId('submit-feedback'));
    
    expect(handleFeedback).toHaveBeenCalledWith('Test question', 'Test answer', 'not_clear');
    expect(screen.getByTestId('feedback-thanks')).toBeInTheDocument();
  });

  it('submits feedback with custom reason', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test question" botResponse="Test answer" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-other'));
    await user.type(screen.getByTestId('custom-reason'), 'Custom feedback reason');
    await user.click(screen.getByTestId('submit-feedback'));
    
    expect(handleFeedback).toHaveBeenCalledWith('Test question', 'Test answer', 'Custom feedback reason');
    expect(screen.getByTestId('feedback-thanks')).toBeInTheDocument();
  });

  it('validates custom reason is required when "Other" is selected', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-other'));
    await user.click(screen.getByTestId('submit-feedback'));
    
    // Should not submit feedback
    expect(handleFeedback).not.toHaveBeenCalled();
    expect(screen.getByTestId('feedback-dialog')).toBeInTheDocument();
  });

  it('cancels feedback dialog', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-not-correct'));
    await user.click(screen.getByTestId('cancel-feedback'));
    
    expect(screen.queryByTestId('feedback-dialog')).not.toBeInTheDocument();
    expect(handleFeedback).not.toHaveBeenCalled();
  });

  it('clears selection when dialog is cancelled', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-not-correct'));
    await user.click(screen.getByTestId('cancel-feedback'));
    
    // Reopen dialog to verify selection is cleared
    await user.click(screen.getByTestId('feedback-no'));
    expect(screen.getByTestId('reason-not-correct')).not.toHaveClass('selected');
  });

  it('hides custom reason when switching from Other to predefined reason', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-other'));
    expect(screen.getByTestId('custom-reason')).toBeInTheDocument();
    
    await user.click(screen.getByTestId('reason-not-correct'));
    expect(screen.queryByTestId('custom-reason')).not.toBeInTheDocument();
  });

  it('handles multiple feedback submissions on same message', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    // Submit positive feedback
    await user.click(screen.getByTestId('feedback-yes'));
    expect(screen.getByTestId('feedback-thanks')).toBeInTheDocument();
    
    // Reset and submit negative feedback
    rerender(<FeedbackComponent userMessage="Test2" botResponse="Response2" />);
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-not-relevant'));
    await user.click(screen.getByTestId('submit-feedback'));
    
    expect(handleFeedback).toHaveBeenCalledTimes(2);
  });

  it('handles long custom feedback', async () => {
    const user = userEvent.setup();
    const longFeedback = 'A'.repeat(1000);
    
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-other'));
    await user.type(screen.getByTestId('custom-reason'), longFeedback);
    await user.click(screen.getByTestId('submit-feedback'));
    
    expect(handleFeedback).toHaveBeenCalledWith('Test', 'Response', longFeedback);
  });

  it('handles special characters in custom feedback', async () => {
    const user = userEvent.setup();
    const specialFeedback = 'Feedback with & < > " \' characters';
    
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('reason-other'));
    await user.type(screen.getByTestId('custom-reason'), specialFeedback);
    await user.click(screen.getByTestId('submit-feedback'));
    
    expect(handleFeedback).toHaveBeenCalledWith('Test', 'Response', specialFeedback);
  });

  it('prevents submission without selecting a reason', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    await user.click(screen.getByTestId('submit-feedback'));
    
    expect(handleFeedback).not.toHaveBeenCalled();
    expect(screen.getByTestId('feedback-dialog')).toBeInTheDocument();
  });

  it('handles keyboard navigation', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    // Tab to Yes button and press Enter
    screen.getByTestId('feedback-yes').focus();
    await user.keyboard('{Enter}');
    
    expect(handleFeedback).toHaveBeenCalledWith('Test', 'Response', 'helpful');
  });

  it('maintains focus state in dialog', async () => {
    const user = userEvent.setup();
    render(<FeedbackComponent userMessage="Test" botResponse="Response" />);
    
    await user.click(screen.getByTestId('feedback-no'));
    
    const firstReason = screen.getByTestId('reason-not-correct');
    firstReason.focus();
    expect(firstReason).toHaveFocus();
  });
});