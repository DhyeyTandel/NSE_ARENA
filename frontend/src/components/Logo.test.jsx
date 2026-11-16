import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Logo } from './Logo';

describe('Logo', () => {
  it('renders the mark at the requested size with an accessible name', () => {
    const { container } = render(<Logo size={40} />);
    expect(screen.getByRole('img', { name: 'NSE Arena' })).toBeTruthy();
    const svg = container.querySelector('svg');
    expect(svg.getAttribute('width')).toBe('40');
    expect(svg.getAttribute('height')).toBe('40');
    expect(container.textContent).toBe('');
  });

  it('shows the wordmark only in the full variant', () => {
    const { container } = render(<Logo variant="full" />);
    expect(container.textContent).toBe('NSE Arena');
    expect(container.querySelector('.logo-word-light').textContent).toBe('Arena');
  });
});
