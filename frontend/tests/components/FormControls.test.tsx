import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { describe, expect, it } from 'vitest';
import { Input } from '../../src/components/ui/Input';
import { Select } from '../../src/components/ui/Select';
import { Textarea } from '../../src/components/ui/Textarea';

describe('Form Controls Components', () => {
  describe('Input', () => {
    it('associates label with input using htmlFor and id', () => {
      render(<Input label="Email Address" id="email-field" />);
      const input = screen.getByLabelText(/email address/i);
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute('id', 'email-field');
    });

    it('renders required indicator when required is true', () => {
      render(<Input label="Full Name" required />);
      expect(screen.getByText('*')).toBeInTheDocument();
    });

    it('renders error message with role="alert" and aria-invalid="true"', () => {
      render(
        <Input
          label="Password"
          error="Password must be at least 8 characters"
        />
      );
      const input = screen.getByLabelText(/password/i);
      const alert = screen.getByRole('alert');

      expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(alert).toHaveTextContent('Password must be at least 8 characters');
    });

    it('renders helper text when no error is present', () => {
      render(
        <Input
          label="Username"
          helperText="Enter your university student ID"
        />
      );
      expect(
        screen.getByText('Enter your university student ID')
      ).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('Select', () => {
    const options = [
      { value: 'cat-1', label: 'Audio-Visual' },
      { value: 'cat-2', label: 'Electrical & Lighting' },
    ];

    it('renders options correctly with label association', () => {
      render(<Select label="Issue Category" options={options} />);
      const select = screen.getByLabelText(/issue category/i);
      expect(select).toBeInTheDocument();
      expect(screen.getByText('Audio-Visual')).toBeInTheDocument();
      expect(screen.getByText('Electrical & Lighting')).toBeInTheDocument();
    });

    it('displays error message and sets aria-invalid on error', () => {
      render(
        <Select
          label="Category"
          options={options}
          error="Please select an issue category"
        />
      );
      const select = screen.getByLabelText(/category/i);
      expect(select).toHaveAttribute('aria-invalid', 'true');
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Please select an issue category'
      );
    });
  });

  describe('Textarea', () => {
    it('associates label with textarea', () => {
      render(<Textarea label="Incident Description" />);
      const textarea = screen.getByLabelText(/incident description/i);
      expect(textarea).toBeInTheDocument();
    });

    it('updates character counter as user types', async () => {
      const user = userEvent.setup();
      const ControlledWrapper = () => {
        const [val, setVal] = React.useState('');
        return (
          <Textarea
            label="Notes"
            value={val}
            onChange={(e) => setVal(e.target.value)}
            showCount
            minChars={10}
            maxLength={100}
          />
        );
      };

      render(<ControlledWrapper />);
      const textarea = screen.getByLabelText(/notes/i);

      expect(screen.getByText(/0 \(min 10\) \/ 100/i)).toBeInTheDocument();

      await user.type(textarea, 'Hello CampusFix');
      expect(screen.getByText(/15 \(min 10\) \/ 100/i)).toBeInTheDocument();
    });

    it('renders error message with role="alert"', () => {
      render(
        <Textarea
          label="Resolution Notes"
          error="Notes must detail the resolution actions taken"
        />
      );
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Notes must detail the resolution actions taken'
      );
    });
  });
});
