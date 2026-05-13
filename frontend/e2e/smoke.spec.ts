import { expect, test } from "@playwright/test";

test.describe("Auth shell @smoke", () => {
  test("anonymous visit to / redirects to /login @smoke", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login(\?|$)/);
    await expect(page.getByText(/ASM V2/)).toBeVisible();
    await expect(page.getByRole("button", { name: /iniciar sesión/i })).toBeVisible();
  });

  test("login renders the brand + form fields @smoke", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/contraseña/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /¿olvidaste tu contraseña\?/i })).toBeVisible();
  });
});
