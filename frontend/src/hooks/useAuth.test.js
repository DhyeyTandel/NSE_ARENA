import { describe, it, expect } from 'vitest';
import { formatApiError } from './useAuth';

describe('formatApiError', () => {
  it('passes string details through', () => {
    expect(formatApiError('Username already registered', 'x')).toBe('Username already registered');
  });

  it('flattens FastAPI 422 detail lists into readable text', () => {
    const detail = [
      { loc: ['body', 'password'], msg: 'String should have at least 8 characters', type: 'string_too_short' },
      { loc: ['body', 'username'], msg: 'String should match pattern', type: 'string_pattern_mismatch' },
    ];
    expect(formatApiError(detail, 'x')).toBe(
      'password: String should have at least 8 characters. username: String should match pattern',
    );
  });

  it('falls back when detail is missing or empty', () => {
    expect(formatApiError(undefined, 'Registration failed')).toBe('Registration failed');
    expect(formatApiError([], 'Registration failed')).toBe('Registration failed');
  });
});
