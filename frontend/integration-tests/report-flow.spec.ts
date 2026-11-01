import { createHmac } from 'node:crypto';
import { test, expect } from '@playwright/test';

const owner = '00000000-0000-4000-8000-000000000001';
function token(subject: string) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ sub: subject, aud: 'authenticated', role: 'authenticated',
    iss: 'https://isolated-project.supabase.test/auth/v1', exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `${header}.${payload}.${createHmac('sha256', 'isolated-browser-test-secret-never-used-in-runtime').update(`${header}.${payload}`).digest('base64url')}`;
}

test('browser submits private media, polls the real API/worker, clarifies, reviews and reloads its result', async ({ page }) => {
  const user = { id: owner, aud: 'authenticated', role: 'authenticated', email: 'isolated-test@example.invalid' };
  await page.addInitScript(({ accessToken, user }) => {
    localStorage.setItem('sb-isolated-project-auth-token', JSON.stringify({ access_token: accessToken,
      refresh_token: 'isolated-refresh-token', expires_at: Math.floor(Date.now() / 1000) + 3600,
      expires_in: 3600, token_type: 'bearer', user }));
  }, { accessToken: token(owner), user });
  await page.route('https://isolated-project.supabase.test/auth/**', async route => {
    await route.fulfill({ json: user });
  });
  await page.route('https://isolated-project.supabase.test/storage/v1/object/upload/sign/**', async route => {
    expect(route.request().headers().authorization).toBeUndefined();
    const id = new URL(route.request().url()).pathname.split('/').at(-1);
    const response = await page.request.put(`http://127.0.0.1:8766/__test_uploads/${id}`, { data: route.request().postDataBuffer()! });
    await route.fulfill({ response });
  });
  await page.goto('/report');
  await page.getByLabel('Location name').fill('Isolated test location');
  await page.getByLabel('Latitude', { exact: true }).fill('1');
  await page.getByLabel('Longitude', { exact: true }).fill('2');
  await page.getByRole('checkbox', { name: 'I have confirmed the latitude and longitude.' }).check();
  await page.getByRole('button', { name: 'Confirm location', exact: true }).click();
  await page.getByLabel('Photograph (required)').setInputFiles({ name: 'isolated.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+XfXkAAAAASUVORK5CYII=', 'base64') });
  await page.getByLabel('Description (optional)').fill('Discarded bags cover the pavement.');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByLabel('Short title (optional)').fill('needs-clarification');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Submit report', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Private report', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'More information needed' })).toBeVisible({ timeout: 15000 });
  await page.getByLabel('Your answer', { exact: true }).fill('The bags remain on the pavement.');
  await page.getByRole('combobox', { name: 'Confirm category', exact: true }).selectOption('garbage');
  await page.getByRole('button', { name: 'Submit answer', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and continue', exact: true })).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: 'Approve and continue', exact: true }).click();
  await expect(page.getByText('authority_unavailable', { exact: true })).toBeVisible({ timeout: 15000 });
  const id = (await page.getByText(/^Report ID:/).textContent())!.split(': ')[1];
  await page.goto(`/reports/${id}`);
  await expect(page.getByText('authority_unavailable', { exact: true })).toBeVisible();
  const denied = await page.request.get(`http://127.0.0.1:8766/reports/${id}`, {
    headers: { Authorization: `Bearer ${token('00000000-0000-4000-8000-000000000002')}` },
  });
  expect(denied.status()).toBe(403);
  await page.goto('/profile');
  await expect(page.getByRole('link', { name: /needs-clarification/ })).toBeVisible();
  await page.getByRole('button', { name: 'Manage account', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Guest', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: /needs-clarification/ })).toHaveCount(0);
});
