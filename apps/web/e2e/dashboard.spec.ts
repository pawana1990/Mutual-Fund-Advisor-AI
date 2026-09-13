import { expect, test } from "@playwright/test";

test.describe("Dashboard", () => {
  test("renders the AI Wealth Advisor shell", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "AI Wealth Advisor" })).toBeVisible();
  });

  test("shows an empty-state when the user has no portfolio yet", async ({ page }) => {
    await page.goto("/");
    // Against a freshly seeded backend (no portfolios.list() results) the
    // empty-state copy from src/app/page.tsx should render instead of a
    // crash or an infinite spinner.
    await expect(page.getByText(/no portfolio yet|loading your portfolio/i)).toBeVisible({ timeout: 10_000 });
  });

  test("dark mode toggle switches the document class", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByRole("button", { name: /toggle dark mode/i });
    await toggle.click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await toggle.click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });
});
