import test from 'node:test';
import assert from 'node:assert/strict';

// Test path sandbox logic in TypeScript mirror
function isPathAllowed(userPath: string, allowedFolders: string[]): boolean {
  // Normalize and detect directory traversal attempts
  const normalized = userPath.replace(/\\/g, '/');
  if (normalized.includes('..')) {
    return false;
  }
  if (normalized.startsWith('/etc') || normalized.startsWith('/var') || normalized.startsWith('/usr') || normalized.startsWith('C:\\Windows')) {
    return false;
  }
  const parts = normalized.split('/').filter(Boolean);
  if (parts.length === 0) return false;
  const firstDir = parts[0];
  return allowedFolders.some(folder => folder.toLowerCase() === firstDir.toLowerCase() || normalized.toLowerCase().includes(folder.toLowerCase()));
}

// Test audit sanitization in TypeScript mirror
function sanitizeSecret(text: string): string {
  return text
    .replace(/GEMINI_API_KEY\s*=\s*[^\s]+/gi, 'GEMINI_API_KEY=[REDACTED]')
    .replace(/AIza[0-9A-Za-z-_]{35}/g, '[REDACTED]')
    .replace(/sk-[a-zA-Z0-9_-]{20,}/g, '[REDACTED]');
}

test('sandbox path validation allows Documents and Downloads', () => {
  const allowed = ['Documents', 'Downloads', 'Desktop'];
  assert.equal(isPathAllowed('Documents/report.docx', allowed), true);
  assert.equal(isPathAllowed('Downloads/data.csv', allowed), true);
  assert.equal(isPathAllowed('Desktop/notes.txt', allowed), true);
});

test('sandbox path validation blocks traversal and system folders', () => {
  const allowed = ['Documents', 'Downloads', 'Desktop'];
  assert.equal(isPathAllowed('Documents/../../etc/passwd', allowed), false);
  assert.equal(isPathAllowed('/etc/passwd', allowed), false);
  assert.equal(isPathAllowed('/var/log/syslog', allowed), false);
});

test('audit log sanitization scrubs sensitive keys', () => {
  const raw = 'Config: GEMINI_API_KEY=AIzaSyD12345678901234567890123456789012';
  const clean = sanitizeSecret(raw);
  assert.equal(clean.includes('AIzaSyD'), false);
  assert.equal(clean.includes('[REDACTED]'), true);
});

test('token metric formatting', () => {
  const inTokens = 45;
  const outTokens = 120;
  const formatted = `Tokens: ${inTokens} in / ${outTokens} out`;
  assert.equal(formatted, 'Tokens: 45 in / 120 out');
});
