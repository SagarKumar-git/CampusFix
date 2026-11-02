import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AlertBanner } from '../../src/components/ui/AlertBanner';

describe('AlertBanner Component', () => {
  it('renders with appropriate role="alert" for error and warning variants', () => {
    const { rerender } = render(
      <AlertBanner variant="error" title="Validation Failed">
        Please check your input.
      </AlertBanner>
    );

    const errorAlert = screen.getByRole('alert');
    expect(errorAlert).toBeInTheDocument();
    expect(screen.getByText('Validation Failed')).toBeInTheDocument();

    rerender(
      <AlertBanner variant="warning" title="Warning Heading">
        Caution required.
      </AlertBanner>
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders with role="status" for info and success variants', () => {
    const { rerender } = render(
      <AlertBanner variant="success" title="Success!">
        Ticket resolved successfully.
      </AlertBanner>
    );

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    rerender(
      <AlertBanner variant="info" title="Info">
        Informational note.
      </AlertBanner>
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('handles dismiss action callback', async () => {
    const user = userEvent.setup();
    const handleDismiss = vi.fn();

    render(
      <AlertBanner
        variant="error"
        title="Dismissable Error"
        onDismiss={handleDismiss}
      >
        Click to dismiss.
      </AlertBanner>
    );

    const closeBtn = screen.getByRole('button', { name: /dismiss alert/i });
    await user.click(closeBtn);
    expect(handleDismiss).toHaveBeenCalledTimes(1);
  });
});
