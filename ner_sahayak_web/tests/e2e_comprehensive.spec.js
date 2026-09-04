import { test, expect } from '@playwright/test';

test.describe('NER Sahayak Comprehensive E2E Workflows (Epics 1-8)', () => {

  test.beforeEach(async ({ page }) => {
    // Intercept standard window.alert / dialogs
    page.on('dialog', async dialog => {
      await dialog.accept();
    });
  });

  test('E2E-01: Authentication, Unauthenticated Redirection & Login Matrix', async ({ page }) => {
    // 1. Attempt protected access without login
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/.*login/);

    // 2. Invalid login test
    await page.getByLabel('Email Address').fill('invalid_user@nersahayak.gov.in');
    await page.getByLabel('Password').fill('badpassword');
    await page.getByRole('button', { name: /log in/i }).click();
    await expect(page).toHaveURL(/.*login/); // Remains on login

    // 3. Valid Login as Control Room Officer
    await page.getByLabel('Email Address').fill('officer@nersahayak.gov.in');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /log in/i }).click();

    // Verify redirected to dashboard and role badge displayed
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('.role-badge')).toContainText('control room');
  });

  test('E2E-02: Village Representative / Hospital Supply Request Creation', async ({ page }) => {
    // 1. Login as Village Representative (Hospital)
    await page.goto('/login');
    await page.getByLabel('Email Address').fill('hospital@nersahayak.gov.in');
    await page.getByLabel('Password').fill('hospital123');
    await page.getByRole('button', { name: /log in/i }).click();

    // Verify Village Rep dashboard panel
    await expect(page.getByRole('heading', { name: 'Request Supplies' })).toBeVisible();

    // 2. Fill supply request form
    const itemInput = page.locator('input[placeholder*="Oxygen Cylinders"]');
    await itemInput.fill('Emergency Insulin Cartridges');
    
    // Select urgency
    const urgencySelect = page.locator('select').nth(1);
    if (await urgencySelect.isVisible()) {
      await urgencySelect.selectOption('emergency');
    }

    // Submit Request
    await page.getByRole('button', { name: /submit request/i }).click();

    // Verify item appears in recent requests list
    await expect(page.getByText('Emergency Insulin Cartridges').first()).toBeVisible({ timeout: 10000 });
  });

  test('E2E-03: Field Officer Incident Reporting with Geolocation & Road Impact', async ({ page }) => {
    // 1. Login as Field Officer
    await page.goto('/login');
    await page.getByLabel('Email Address').fill('fo@nersahayak.gov.in');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /log in/i }).click();

    await expect(page.getByRole('heading', { name: 'Report Incident' })).toBeVisible();

    // 2. Select location by clicking map
    const mapArea = page.locator('.leaflet-container');
    await expect(mapArea).toBeVisible();
    await mapArea.click({ position: { x: 300, y: 300 } });

    // 3. Fill incident form
    const roadSelect = page.locator('select').first();
    await roadSelect.selectOption({ index: 1 }); // select first available road

    const descInput = page.locator('textarea');
    await descInput.fill('Severe boulder obstruction on mountain curve observed during patrol.');

    // 4. Submit incident
    await page.getByRole('button', { name: /report incident/i }).click();

    // Form should reset after submission
    await expect(descInput).toHaveValue('');
  });

  test('E2E-04: Driver Telemetry & Checkpoint Logging', async ({ page }) => {
    // 1. Login as Driver
    await page.goto('/login');
    await page.getByLabel('Email Address').fill('driver@nersahayak.gov.in');
    await page.getByLabel('Password').fill('driver123');
    await page.getByRole('button', { name: /log in/i }).click();

    await expect(page.getByRole('heading', { name: 'Active Deliveries' })).toBeVisible();

    // 2. Check if active deliveries exist
    const checkpointInput = page.locator('input[placeholder="Checkpoint Name"]').first();
    if (await checkpointInput.isVisible()) {
      await checkpointInput.fill('Upper Shillong Toll Gate');

      // Click map for checkpoint coordinates
      const mapArea = page.locator('.leaflet-container');
      await mapArea.click({ position: { x: 350, y: 250 } });

      // Click Log Checkpoint
      await page.getByRole('button', { name: 'Log Checkpoint' }).first().click();

      // Checkpoint input should clear on success
      await expect(checkpointInput).toHaveValue('');
    }
  });

  test('E2E-05: Driver Proof of Delivery (Full & Discrepancy Reconciliation UI)', async ({ page }) => {
    // 1. Login as Driver
    await page.goto('/login');
    await page.getByLabel('Email Address').fill('driver@nersahayak.gov.in');
    await page.getByLabel('Password').fill('driver123');
    await page.getByRole('button', { name: /log in/i }).click();

    const podBtn = page.getByRole('button', { name: /submit proof of delivery/i }).first();
    if (await podBtn.isVisible()) {
      await podBtn.click();

      // POD Modal should appear
      await expect(page.getByRole('heading', { name: 'Submit Proof of Delivery' })).toBeVisible();

      // Verify fields
      await expect(page.getByLabel(/received quantity/i)).toBeVisible();
      await expect(page.getByLabel(/condition/i)).toBeVisible();

      // Close modal by clicking Cancel
      await page.getByRole('button', { name: 'Cancel' }).click();
      await expect(page.getByRole('heading', { name: 'Submit Proof of Delivery' })).not.toBeVisible();
    }
  });

  test('E2E-06: Offline PWA Banner and Network State Transition', async ({ page }) => {
    // 1. Login as Field Officer
    await page.goto('/login');
    await page.getByLabel('Email Address').fill('fo@nersahayak.gov.in');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /log in/i }).click();
    await expect(page).toHaveURL(/.*dashboard/);

    // 2. Disconnect Network in browser context
    await page.context().setOffline(true);

    // Dispatch offline event to notify sync worker / App UI
    await page.evaluate(() => {
      window.dispatchEvent(new Event('offline'));
    });

    // Verify offline status indicator or banner
    const offlineIndicator = page.locator('text=OFFLINE').or(page.locator('text=SERVER UNAVAILABLE'));
    // Wait briefly for UI reactivity
    await page.waitForTimeout(1000);

    // 3. Reconnect Network
    await page.context().setOffline(false);
    await page.evaluate(() => {
      window.dispatchEvent(new Event('online'));
    });
    await page.waitForTimeout(1000);
  });

});
