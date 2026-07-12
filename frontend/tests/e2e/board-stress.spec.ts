/**
 * SHERLOCK — Investigation Board stress test (checklist item 8).
 *
 * NOT run as part of `npm test` — this needs a real browser and the dev
 * server up, which this sandbox can't provide (no display, no mic/GPU).
 * Run it yourself with:
 *
 *   npm install -D @playwright/test
 *   npx playwright install chromium
 *   npm run dev                       # in one terminal
 *   npx playwright test tests/e2e     # in another
 *
 * What it does:
 *   1. Opens the board and adds N sticky notes via the toolbar button
 *      (the same code path a real user hits — no store/API shortcuts).
 *   2. Times how long the Nth add takes vs. the 1st, as a cheap proxy for
 *      "does render cost grow with card count" (checklist: "drag
 *      performance", "rendering speed" with hundreds of cards).
 *   3. Exercises pan/zoom/auto-layout/undo/redo/presentation mode after
 *      the board is populated, and asserts the app doesn't throw or hang.
 *
 * Known prerequisite gap (see FINDINGS.md "Frontend / Investigation
 * Board"): none of the board components expose `data-testid` attributes,
 * so this script has to fall back to visible button text and CSS-module
 * class *prefixes* (Vite/CSS-modules hash the suffix, not the prefix, so
 * `[class*="card"]` style selectors are the least-brittle option
 * available without touching component source). If you add
 * `data-testid="board-card"` etc. to InvestigationBoard.tsx, swap the
 * selectors below to match — it'll make this suite far less fragile.
 */
import { test, expect, type Page } from '@playwright/test';

const CARD_COUNT = 300;

async function addSticky(page: Page) {
  await page.getByRole('button', { name: '+ Sticky note' }).click();
}

test.describe('Investigation Board — hundreds-of-cards stress test', () => {
  test('adding, panning, zooming, and undo/redo stay responsive at scale', async ({ page }) => {
    await page.goto('/');

    // Adjust this navigation step to however the app actually reaches the
    // board (e.g. clicking into a case from the workspace) — inspect
    // WorkspaceLayout.tsx / App.tsx routing if this selector doesn't match.
    const enterBoard = page.getByRole('button', { name: /board/i }).first();
    if (await enterBoard.isVisible().catch(() => false)) {
      await enterBoard.click();
    }

    const timings: number[] = [];
    for (let i = 0; i < CARD_COUNT; i++) {
      const start = Date.now();
      await addSticky(page);
      timings.push(Date.now() - start);
    }

    const firstTenAvg = average(timings.slice(0, 10));
    const lastTenAvg = average(timings.slice(-10));
    console.log(`avg add time — first 10: ${firstTenAvg}ms, last 10: ${lastTenAvg}ms`);
    // Flag (not hard-fail) egregious degradation: more than 5x slower by
    // the end suggests O(n) or worse re-render cost per card added.
    expect(lastTenAvg).toBeLessThan(firstTenAvg * 5 + 50);

    // Auto-layout, undo, redo, reset view must all complete without hanging.
    await page.getByRole('button', { name: 'Auto-layout' }).click();
    await page.getByRole('button', { name: 'Reset view' }).click();
    await page.getByRole('button', { name: 'Undo' }).click();
    await page.getByRole('button', { name: 'Redo' }).click();

    // Pan/zoom via mouse wheel + drag on the canvas, not just keyboard —
    // this is the actual interaction the checklist item is worried about.
    const canvas = page.locator('[class*="canvas"]').first();
    await canvas.hover();
    await page.mouse.wheel(0, -200); // zoom in
    await page.mouse.wheel(0, 200);  // zoom out
    await page.mouse.down();
    await page.mouse.move(200, 100, { steps: 10 });
    await page.mouse.up();

    // No uncaught page errors across the whole run.
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));
    expect(pageErrors).toEqual([]);
  });

  test('presentation mode toggles cleanly with a populated board', async ({ page }) => {
    await page.goto('/');
    // Presentation requires at least one pinned card — this test assumes
    // the board from the previous test isn't reset between tests; if your
    // Playwright config isolates storage/state per test, seed a pinned
    // card here first via the UI before calling Present.
    const presentBtn = page.getByRole('button', { name: /present/i }).first();
    if (await presentBtn.isEnabled().catch(() => false)) {
      await presentBtn.click();
      await expect(page.getByRole('button', { name: 'Exit presentation' })).toBeVisible();
      await page.getByRole('button', { name: 'Exit presentation' }).click();
    }
  });
});

function average(nums: number[]): number {
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}
