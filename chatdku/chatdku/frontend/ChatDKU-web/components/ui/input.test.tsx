import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from './input';

describe('Input', () => {
  it('renders with default props', () => {
    render(<Input />);
    const input = screen.getByRole('textbox');
    expect(input).toBeInTheDocument();
  });

  it('renders with placeholder', () => {
    render(<Input placeholder="Enter text" />);
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toBeInTheDocument();
  });

  it('handles value changes', async () => {
    const user = userEvent.setup();
    render(<Input />);
    const input = screen.getByRole('textbox');
    await user.type(input, 'Hello');
    expect(input).toHaveValue('Hello');
  });

  it('applies custom className', () => {
    render(<Input className="custom-class" />);
    const input = screen.getByRole('textbox');
    expect(input).toHaveClass('custom-class');
  });

  it('renders with different type', () => {
    render(<Input type="password" />);
    const input = screen.getByDisplayValue('');
    expect(input).toHaveAttribute('type', 'password');
  });
});