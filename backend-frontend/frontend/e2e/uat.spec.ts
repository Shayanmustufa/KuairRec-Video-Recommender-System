import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

// End-user acceptance scenarios (WBS Day 11 smoke test, Day 13 UAT). Screenshots
// are written to docs/evidence/screenshots as demo evidence.
const SHOTS = path.resolve(__dirname, '../../docs/evidence/screenshots');

async function shot(page: Page, name: string) {
  const project = test.info().project.name.replace('-chromium', '');
  await page.screenshot({ path: path.join(SHOTS, `${project}-${name}.png`), fullPage: true });
}

function trackConsole(page: Page) {
  const errors: string[] = [];
  page.on('console', (msg) => msg.type() === 'error' && errors.push(msg.text()));
  page.on('pageerror', (err) => errors.push(err.message));
  return errors;
}

async function loadUser(page: Page, id: string) {
  await page.getByLabel('Or enter any user ID').fill(id);
  await page.getByRole('button', { name: 'Load' }).click();
}

const cards = (page: Page) => page.getByTestId('recommendation-card');

test('UAT-01 known user receives top-10 recommendations with visible evidence', async ({ page }) => {
  const errors = trackConsole(page);
  await page.goto('/');
  await loadUser(page, '0');
  await expect(cards(page)).toHaveCount(10);
  await expect(page.getByTestId('state-banner')).toContainText('Personalised recommendations');
  await expect(page.getByText('model: hybrid-validation-selected-v1')).toBeVisible();
  const first = cards(page).first();
  await expect(first.getByText('Rank #1')).toBeVisible();
  await expect(first.locator('[data-reason-code="liked_by_similar_users"]')).toBeVisible();
  await expect(first.getByRole('table', { name: 'Hybrid score breakdown' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Hybrid explanation' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Recommendation evidence — user 0/ })).toBeVisible();
  await shot(page, 'uat01-known-user');
  expect(errors).toEqual([]);
});

test('UAT-02 unknown user gets an explicit cold-start fallback', async ({ page }) => {
  await page.goto('/');
  await loadUser(page, 'brand-new-user');
  await expect(page.getByTestId('state-banner')).toContainText('Unknown user “brand-new-user”');
  await expect(cards(page).first().locator('[data-reason-code="cold_start"]')).toBeVisible();
  await expect(page.getByText('fallback: yes')).toBeVisible();
  await shot(page, 'uat02-unknown-user');
});

test('UAT-03 known user without positive history is labelled and falls back', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Demo user').selectOption('735');
  await expect(page.getByTestId('state-banner')).toContainText('No positive history');
  await expect(cards(page).first().locator('[data-reason-code="cold_start"]')).toBeVisible();
  await shot(page, 'uat03-no-history-user');
});

test('UAT-04 cold-start toggle, top-K, sort and refresh controls work', async ({ page }) => {
  await page.goto('/');
  await loadUser(page, '0');
  await expect(cards(page)).toHaveCount(10);
  await page.getByLabel('Top-K').selectOption('5');
  await expect(cards(page)).toHaveCount(5);
  await page.getByLabel('Sort shown results').selectOption('popularity');
  await expect(cards(page)).toHaveCount(5);
  await page.getByRole('button', { name: 'Refresh' }).click();
  await expect(cards(page)).toHaveCount(5);
  await page.getByLabel('Cold-start view (popularity fallback)').check();
  await expect(page.getByTestId('state-banner')).toContainText('Cold-start view requested');
  await shot(page, 'uat04-cold-start-toggle');
});

test('UAT-05 per-request model switch and comparison route', async ({ page, request }) => {
  await page.goto('/');
  await page.getByLabel('Model (this request only)').selectOption('item-cf-cosine-v1');
  await expect(page.getByText('model: item-cf-cosine-v1')).toBeVisible();
  await expect(page.getByText('split: validation')).toBeVisible();
  const current = await (await request.get('/api/v1/models/current')).json();
  expect(current.active_default_model).toBe('hybrid-validation-selected-v1'); // no shared-state change
  await page.goto('/compare');
  for (const name of ['Popularity', 'Item-CF', 'LightGCN (rejected)', 'Hybrid (selected)']) {
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  }
  await shot(page, 'uat05-compare');
});

test('UAT-06 feedback is persisted and queryable', async ({ page, request }) => {
  await page.goto('/');
  await loadUser(page, '0');
  const first = cards(page).first();
  await first.getByRole('button', { name: /^Play video/ }).click();
  await expect(first.getByText('Recorded “play”')).toBeVisible();
  const body = await (await request.get('/api/v1/feedback?user_id=0&limit=5')).json();
  expect(body.events[0].action).toBe('play');
  expect(body.events[0].request_id).not.toBe('');
  await shot(page, 'uat06-feedback');
});

test('UAT-07 video detail shows official metadata and Item-CF neighbours', async ({ page }) => {
  await page.goto('/videos/5434');
  await expect(page.getByRole('heading', { name: 'Official catalog metadata' })).toBeVisible();
  await expect(page.getByText('watch_ratio > 2.0', { exact: false }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Similar items (Item-CF)' })).toBeVisible();
  await expect(page.getByText(/^cosine /).first()).toBeVisible();
  await shot(page, 'uat07-video-detail');
  await page.goto('/videos/999999');
  await expect(page.getByText('Video 999999 is not in the eligible KuaiRec catalog.')).toBeVisible();
});

test('UAT-08 metrics and system routes show evaluation and live status', async ({ page }) => {
  await page.goto('/metrics');
  await expect(page.getByRole('heading', { name: /Controlled test pass/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Validation / test split summary' })).toBeVisible();
  await shot(page, 'uat08-metrics');
  await page.goto('/system');
  await expect(page.getByText('ready', { exact: true })).toBeVisible();
  await expect(page.getByText('checksums verified at load: yes', { exact: false })).toBeVisible();
  await shot(page, 'uat08-system');
});

test('UAT-09 backend-unavailable and timeout states', async ({ page }) => {
  await page.route('**/api/v1/recommendations', (route) => route.abort('connectionrefused'));
  await page.goto('/');
  await expect(page.getByRole('alert').filter({ hasText: 'Backend unavailable' })).toBeVisible();
  await shot(page, 'uat09-backend-unavailable');
  await page.unroute('**/api/v1/recommendations');
  await page.route('**/api/v1/recommendations', () => undefined); // never answers
  await page.getByRole('button', { name: 'Refresh' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'did not respond in time' })).toBeVisible({ timeout: 15_000 });
  await shot(page, 'uat09-timeout');
});

test('UAT-10 keyboard basics: skip link and labelled controls', async ({ page, isMobile }) => {
  test.skip(isMobile, 'keyboard check runs on desktop');
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  for (const label of ['Demo user', 'Model (this request only)', 'Top-K', 'Sort shown results']) {
    await expect(page.getByLabel(label)).toBeVisible();
  }
});

test('UAT-11 every route renders without console errors or horizontal overflow', async ({ page }) => {
  const errors = trackConsole(page);
  for (const route of ['/', '/compare', '/metrics', '/system', '/videos/5434']) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1').first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${route} horizontal overflow`).toBeLessThanOrEqual(1);
  }
  expect(errors).toEqual([]);
});
