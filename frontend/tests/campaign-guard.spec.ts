import { test, expect } from '@playwright/test';

test('campaign button accessibility and distinct names on list and detail', async ({ page }) => {
  await page.goto('/campaigns');
  // Check distinct accessible names on list view cards
  const schoolBtn = page.getByRole('button', { name: 'Join A safer walk to school campaign' });
  const cornersBtn = page.getByRole('button', { name: 'Join Clean corners, shared responsibility campaign' });
  const rainBtn = page.getByRole('button', { name: 'Join Keep our streets rain-ready campaign' });

  await expect(schoolBtn).toBeVisible();
  await expect(schoolBtn).toHaveAttribute('aria-pressed', 'false');
  await expect(cornersBtn).toBeVisible();
  await expect(rainBtn).toBeVisible();

  // Detail view
  await page.goto('/campaigns/safer-streets');
  const detailBtn = page.getByRole('button', { name: 'Join A safer walk to school campaign' });
  await expect(detailBtn).toBeVisible();
  await expect(detailBtn).toHaveAttribute('aria-pressed', 'false');
});

test('rapid double-click on campaign join produces only one membership change', async ({ page }) => {
  await page.goto('/campaigns');
  const btn = page.getByRole('button', { name: 'Join A safer walk to school campaign' });
  await expect(btn).toBeVisible();

  // Rapid double click
  await Promise.all([
    btn.click(),
    btn.click().catch(() => {}), // second click ignored or button disabled
  ]);

  // Successfully toggles once to Leave campaign
  const leaveBtn = page.getByRole('button', { name: 'Leave A safer walk to school campaign' });
  await expect(leaveBtn).toBeVisible();
  await expect(leaveBtn).toHaveAttribute('aria-pressed', 'true');
});

test('storage failure shows error, preserves membership, and clears pending', async ({ page }) => {
  await page.goto('/campaigns/safer-streets');

  // Inject failure for localStorage.setItem on campaign membership key
  await page.evaluate(() => {
    const origSetItem = localStorage.setItem.bind(localStorage);
    localStorage.setItem = (k: string, v: string) => {
      if (k.startsWith('civicmesh.campaign-membership')) {
        throw new Error('QuotaExceededError');
      }
      return origSetItem(k, v);
    };
  });

  const joinBtn = page.getByRole('button', { name: 'Join A safer walk to school campaign' });
  await joinBtn.click();

  // Shows user-facing error message
  await expect(page.getByRole('status')).toContainText(
    'Your campaign membership could not be saved. Free some browser storage and try again.'
  );

  // Button is no longer pending/disabled
  await expect(joinBtn).toBeEnabled();
  await expect(joinBtn).toHaveAttribute('aria-pressed', 'false');
});

test('successful changes update both list and detail UI reactively', async ({ page }) => {
  await page.goto('/campaigns');
  const listBtn = page.getByRole('button', { name: 'Join Clean corners, shared responsibility campaign' });
  await listBtn.click();

  // Card updates to Leave
  const leaveListBtn = page.getByRole('button', { name: 'Leave Clean corners, shared responsibility campaign' });
  await expect(leaveListBtn).toBeVisible();
  await expect(leaveListBtn).toHaveAttribute('aria-pressed', 'true');

  // Navigate to detail page
  await page.goto('/campaigns/clean-corners');
  const detailBtn = page.getByRole('button', { name: 'Leave Clean corners, shared responsibility campaign' });
  await expect(detailBtn).toBeVisible();
  await expect(detailBtn).toHaveAttribute('aria-pressed', 'true');
});

test('report submission startup and failure show accurate progress messages and no secure claims', async ({ page }) => {
  const photo = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');

  await page.goto('/report');
  await page.getByRole('button', { name: 'Confirm location' }).click();
  await page.getByLabel('Photograph (required)').setInputFiles({ name: 'issue.png', mimeType: 'image/png', buffer: photo });
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();

  // Review step before submit
  const notice = page.locator('p.notice');
  await expect(notice).toContainText('This report has not been sent yet. Review your details before submitting.');
  await expect(notice).not.toContainText('secure');

  // Test failure state: mock citizenService failure
  await page.evaluate(() => {
    const origIndexedDB = window.indexedDB;
    // Break indexedDB or storage so createReport fails
    Object.defineProperty(window, 'indexedDB', {
      get() {
        return null;
      },
    });
    void origIndexedDB;
  });

  await page.getByRole('button', { name: 'Submit report' }).click();

  // After failure: error is shown, progress spinner is removed, no secure claims
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.locator('div[style*="animation: spin"]')).toHaveCount(0);
  await expect(notice).toContainText('This report has not been sent yet. Review your details before submitting.');
  await expect(notice).not.toContainText('secure');
});
