import { test, expect } from "@playwright/test";

/**
 * Login flow e2e.
 *
 * Exercises the full path: Next.js login screen → POST /api/login (proxied
 * to FastAPI) → /api/me → dashboard render.
 *
 * Requires: API on :18001, sandbox tenant seeded (PIN 246810).
 */

test.describe("Login flow", () => {
  test("logs in to the demo sandbox and lands on the dashboard", async ({
    page,
  }) => {
    await page.goto("/login");

    // Step 1: facility code
    await expect(page.getByRole("heading", { name: /enter your pin/i })).toBeHidden();
    await page.getByLabel(/facility code/i).fill("demo-sandbox");
    await page.getByRole("button", { name: /continue/i }).click();

    // Step 2: PIN keypad — type via the digit buttons
    await expect(
      page.getByRole("heading", { name: /enter your pin/i }),
    ).toBeVisible();

    const pin = "246810";
    for (const digit of pin) {
      await page.getByRole("button", { name: `Digit ${digit}` }).click();
    }

    // Should auto-submit and redirect to /dashboard.
    await page.waitForURL("**/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Welcome",
    );
    await expect(page.getByText(/sandbox/i)).toBeVisible();
  });

  test("rejects a wrong PIN and clears the keypad", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/facility code/i).fill("demo-sandbox");
    await page.getByRole("button", { name: /continue/i }).click();

    for (const digit of "000000") {
      await page.getByRole("button", { name: `Digit ${digit}` }).click();
    }

    await expect(page.getByText(/invalid login/i)).toBeVisible();

    // The PIN dots should reset to 0 filled (we cleared on error).
    const filled = await page
      .locator("[role='status'][aria-label*='PIN']")
      .first()
      .getAttribute("aria-label");
    expect(filled).toContain("0 of 6");
  });
});
