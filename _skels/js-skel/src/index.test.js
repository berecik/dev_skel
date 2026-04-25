import { test } from 'node:test';
import assert from 'node:assert';
import { greet } from './index.js';

test('greet returns hello world by default', () => {
  assert.strictEqual(greet(), 'Hello, World!');
});

test('greet returns hello with custom name', () => {
  assert.strictEqual(greet('Developer'), 'Hello, Developer!');
});
