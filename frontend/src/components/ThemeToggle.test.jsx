import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeToggle } from './ThemeToggle';

describe('ThemeToggle', () => {
  beforeEach(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    const store = new Map();
    vi.stubGlobal('localStorage', {
      getItem: k => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => { store.set(k, String(v)); },
      removeItem: k => { store.delete(k); },
    });
  });

  it('flips data-theme on <html>, updates aria-pressed and persists the choice', async () => {
    render(<ThemeToggle />);
    const btn = screen.getByLabelText('Dark theme');
    expect(btn.getAttribute('aria-pressed')).toBe('false');

    fireEvent.click(btn);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('nse-arena-theme')).toBe('dark');
    await waitFor(() => expect(screen.getByLabelText('Dark theme').getAttribute('aria-pressed')).toBe('true'));

    fireEvent.click(screen.getByLabelText('Dark theme'));
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('nse-arena-theme')).toBe('light');
  });
});
