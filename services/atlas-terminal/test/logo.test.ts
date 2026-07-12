import { describe, expect, it } from 'bun:test';
import { go, logos } from '../src/vendor/opencode/cli/logo';

// The Logo renderer derives the right-column offset from left[0] and joins
// left/right rows 1:1, so ANY ragged row shifts glyphs sideways on screen
// (the 2026-07-11 UAT "ATLAS name looks misaligned" defect). Lock uniformity.
describe('logo shapes', () => {
  const shapes = { ...logos, go };

  for (const [name, shape] of Object.entries(shapes)) {
    it(`${name}: all left rows share one width`, () => {
      const widths = shape.left.map((row) => row.length);
      expect(new Set(widths).size).toBe(1);
    });

    it(`${name}: all right rows share one width`, () => {
      const widths = shape.right.map((row) => row.length);
      expect(new Set(widths).size).toBe(1);
    });

    it(`${name}: left and right have the same row count`, () => {
      expect(shape.left.length).toBe(shape.right.length);
    });
  }
});
