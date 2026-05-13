import { expect, test } from "@playwright/test";

test.describe("Placeholder shell @smoke", () => {
  test("renders header, sidebar and placeholder copy @smoke", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("banner")).toBeVisible();
    await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();
    await expect(page.getByText(/ada asm placeholder/i)).toBeVisible();
  });
});
