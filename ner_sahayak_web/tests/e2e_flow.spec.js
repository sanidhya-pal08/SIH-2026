import { test, expect } from '@playwright/test';

test.describe('NER Sahayak E2E Workflows', () => {
  
  test('Epic 1-4: Control Room Officer Flow', async ({ page }) => {
    // 1. Login (Epic 1)
    await page.goto('/');
    
    // Fill credentials and login (Role is determined by backend based on user)
    await page.getByLabel('Email Address').fill('officer@nersahayak.gov.in');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /log in/i }).click();
    
    // Verify Dashboard loads
    await expect(page.getByRole('heading', { name: 'Pending Requests' })).toBeVisible();

    // 2. Sync Weather Data (Epic 4)
    // Intercept the alert so it doesn't block the test
    page.on('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: /sync weather data/i }).click();
    
    // 3. Override Priority (Epic 2)
    // Find the first request card and click Override
    const overrideBtn = page.getByRole('button', { name: 'Override' }).first();
    if (await overrideBtn.isVisible()) {
      await overrideBtn.click();
      
      // Modal should appear
      await expect(page.getByRole('heading', { name: 'Override Priority Score' })).toBeVisible();
      
      // Fill out new score and reason
      await page.getByLabel('New Priority Score (0-100)').fill('99.5');
      await page.getByLabel('Override Rationale (min 15 chars)').fill('Emergency test override reason with sufficient length');
      await page.getByRole('button', { name: 'Apply Override' }).click();
    }

    // 4. Evaluate Route & Dispatch (Epic 3)
    const evalBtn = page.getByRole('button', { name: 'Evaluate Route & Dispatch' }).first();
    if (await evalBtn.isVisible()) {
      await evalBtn.click();
      
      // Route Evaluation Modal should appear
      await expect(page.getByRole('heading', { name: 'Route Evaluation Complete' })).toBeVisible({ timeout: 10000 });
      
      // Verify options table is visible
      await expect(page.locator('table')).toBeVisible();
      
      // Select a driver
      await page.getByRole('combobox', { name: 'Assign Driver' }).selectOption({ index: 1 }); // select first valid driver
      
      // Approve and Dispatch
      await page.getByRole('button', { name: 'Approve & Dispatch' }).click();
      
      // Verification: The request card should disappear or status update (UI optimistic update removes it from pending)
    }
  });

});
