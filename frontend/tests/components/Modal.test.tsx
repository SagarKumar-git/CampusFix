import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Button } from '../../src/components/ui/Button';
import { Modal } from '../../src/components/ui/Modal';

describe('Modal Dialog Component', () => {
  it('renders nothing when isOpen is false', () => {
    render(
      <Modal isOpen={false} onClose={vi.fn()} title="Test Modal">
        <p>Modal Body</p>
      </Modal>
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders with role="dialog", aria-modal="true", and accessible title', () => {
    render(
      <Modal
        isOpen={true}
        onClose={vi.fn()}
        title="Resolve Work Order"
        description="Please confirm resolution details"
      >
        <p>Modal Body</p>
      </Modal>
    );

    const dialog = screen.getByRole('dialog', { name: /resolve work order/i });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(
      screen.getByText('Please confirm resolution details')
    ).toBeInTheDocument();
  });

  it('calls onClose when Escape key is pressed', () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Escape Test">
        <p>Content</p>
      </Modal>
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('does not close on Escape if preventCloseOnEscape is true', () => {
    const handleClose = vi.fn();
    render(
      <Modal
        isOpen={true}
        onClose={handleClose}
        title="No Escape"
        preventCloseOnEscape
      >
        <p>Content</p>
      </Modal>
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(handleClose).not.toHaveBeenCalled();
  });

  it('calls onClose when clicking outside on the backdrop', () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Backdrop Test">
        <p>Content</p>
      </Modal>
    );

    fireEvent.click(screen.getByTestId('modal-backdrop'));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('restores focus to trigger button after modal is closed', async () => {
    const user = userEvent.setup();

    const ModalTestHarness = () => {
      const [isOpen, setIsOpen] = useState(false);
      return (
        <div>
          <button id="open-modal-btn" onClick={() => setIsOpen(true)}>
            Open Dialog
          </button>
          <Modal
            isOpen={isOpen}
            onClose={() => setIsOpen(false)}
            title="Focus Test"
            footer={
              <Button onClick={() => setIsOpen(false)}>Done</Button>
            }
          >
            <input aria-label="First Field" />
          </Modal>
        </div>
      );
    };

    render(<ModalTestHarness />);
    const openBtn = screen.getByRole('button', { name: /open dialog/i });

    // Focus and click open button
    openBtn.focus();
    expect(document.activeElement).toBe(openBtn);

    await user.click(openBtn);

    // Modal should be open
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Close the modal
    const closeBtn = screen.getByRole('button', { name: /close dialog/i });
    await user.click(closeBtn);

    // After closing, focus should be restored to the open button
    await waitFor(() => {
      expect(document.activeElement).toBe(openBtn);
    });
  });

  it('traps keyboard focus inside the modal on Tab and Shift+Tab', async () => {
    render(
      <Modal
        isOpen={true}
        onClose={vi.fn()}
        title="Focus Trap Test"
        footer={
          <Button id="last-focusable">Last Action</Button>
        }
      >
        <input id="first-input" aria-label="First Input" />
      </Modal>
    );

    const closeBtn = screen.getByRole('button', { name: /close dialog/i });
    const lastBtn = screen.getByRole('button', { name: /last action/i });

    // Focus last button and press Tab -> should cycle to closeBtn (first focusable)
    lastBtn.focus();
    expect(document.activeElement).toBe(lastBtn);

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: false });
    expect(document.activeElement).toBe(closeBtn);

    // Focus first focusable and press Shift+Tab -> should cycle to lastBtn
    closeBtn.focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(lastBtn);
  });
});
