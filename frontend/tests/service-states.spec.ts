import { test, expect } from '@playwright/test';

test('unconfigured services show errors and never preload operational records', async ({ page }) => {
  await page.goto('/map');
  await expect(page.getByRole('alert')).toContainText('Backend service is not configured');
  await expect(page.locator('.issue-marker')).toHaveCount(0);
  await expect(page.locator('.issue-row')).toHaveCount(0);
  await expect(page.getByText('Map service is not configured.', { exact: false })).toBeVisible();
});

test('previous demo caches cannot populate the application', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('civicmesh.app.v1', JSON.stringify({
    issues: [{ id: 'isolated-legacy-fixture', title: 'Legacy test record', category: 'Waste',
      coordinates: { lat: 0, lng: 0 } }], campaigns: [{ id: 'legacy', title: 'Legacy test campaign' }],
  })));
  await page.goto('/map');
  await expect(page.getByRole('alert')).toContainText('Backend service is not configured');
  await expect(page.getByText('Legacy test record')).toHaveCount(0);
  await page.goto('/campaigns');
  await expect(page.getByText('No campaigns have been loaded.', { exact: false })).toBeVisible();
  await expect(page.getByText('Legacy test campaign')).toHaveCount(0);
});

test('profile has no fabricated citizen identity or awards', async ({ page }) => {
  await page.goto('/profile');
  await expect(page.getByRole('heading', { name: 'Guest', exact: true })).toBeVisible();
  await expect(page.getByText('Verified badges are not configured.')).toBeVisible();
  await expect(page.getByText('Meera Krishnan')).toHaveCount(0);
});

test('report location requires explicit confirmation and is not prefilled with a locality', async ({ page }) => {
  await page.goto('/report');
  await expect(page.getByLabel('Location name')).toHaveValue('');
  await page.getByRole('button', { name: 'Confirm location', exact: true }).click();
  await expect(page.getByText('Add a location name and confirm the coordinates.')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'I have confirmed the latitude and longitude.' })).not.toBeChecked();
});

test('unconfigured submission never shows a fabricated success', async ({ page }) => {
  await page.goto('/report');
  await page.getByLabel('Location name').fill('Isolated test location');
  await page.getByLabel('Latitude', { exact: true }).fill('1');
  await page.getByLabel('Longitude', { exact: true }).fill('2');
  await page.getByRole('checkbox', { name: 'I have confirmed the latitude and longitude.' }).check();
  await page.getByRole('button', { name: 'Confirm location', exact: true }).click();
  await page.locator('input[type=file]').first().setInputFiles({ name: 'isolated.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+XfXkAAAAASUVORK5CYII=', 'base64') });
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByLabel('Category').locator('option')).toHaveCount(2);
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Submit report', exact: true }).click();
  await expect(page.getByText('Backend service is not configured. Your report has not been submitted.')).toBeVisible();
  await expect(page.getByRole('heading', { name: /Report received/ })).toHaveCount(0);
});

test('neutral viewport coordinates require an explicit selection, including zero', async ({ page }) => {
  await page.goto('/report');
  await page.getByLabel('Location name').fill('Isolated explicit-zero test');
  await page.getByRole('checkbox', { name: 'I have confirmed the latitude and longitude.' }).check();
  await page.getByRole('button', { name: 'Confirm location', exact: true }).click();
  await expect(page.getByText('Add a location name and confirm the coordinates.')).toBeVisible();
  await expect(page.getByLabel('Latitude', { exact: true })).toHaveValue('');
  await page.getByLabel('Latitude', { exact: true }).fill('0');
  await page.getByLabel('Longitude', { exact: true }).fill('0');
  await page.getByRole('checkbox', { name: 'I have confirmed the latitude and longitude.' }).check();
  await page.getByRole('button', { name: 'Confirm location', exact: true }).click();
  await expect(page.getByLabel('Photograph (required)')).toBeVisible();
});

test('coordinate drafts preserve decimal and negative keystrokes until the citizen finishes editing', async ({ page }) => {
  await page.goto('/report');
  await page.getByLabel('Location name').fill('Isolated coordinate-editing test');
  const latitude = page.getByLabel('Latitude', { exact: true });
  const longitude = page.getByLabel('Longitude', { exact: true });
  await latitude.fill('1');
  await longitude.fill('2');
  const confirmation = page.getByRole('checkbox', { name: 'I have confirmed the latitude and longitude.' });
  await confirmation.check();
  await latitude.focus();
  await latitude.press('ControlOrMeta+A');
  await latitude.pressSequentially('28.6139');
  await expect(latitude).toHaveValue('28.6139');
  await expect(confirmation).not.toBeChecked();
  await longitude.focus();
  await longitude.press('ControlOrMeta+A');
  await longitude.pressSequentially('-77.2090');
  await expect(longitude).toHaveValue('-77.2090');
  await confirmation.check();
  await page.getByRole('button', { name: 'Confirm location', exact: true }).click();
  await expect(page.getByLabel('Photograph (required)')).toBeVisible();
});

test('empty service states remain usable at mobile and desktop widths', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/map');
    await expect(page.getByRole('alert')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  expect(errors).toEqual([]);
});
