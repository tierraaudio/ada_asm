import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@singularthings.io";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "admin123";

test.describe("Dashboard shell @smoke", () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate against the live stack (a seeded admin is expected; the
    // local docker compose stack ships with one).
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
    await page.getByLabel(/contraseña/i).fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /iniciar sesión/i }).click();
    await expect(page).toHaveURL("/");
  });

  test("sidebar toggle persists across reload @smoke", async ({ page }) => {
    // Sidebar visible by default.
    await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();

    // Collapse it.
    await page.getByRole("button", { name: /ocultar menú lateral/i }).click();
    await expect(page.getByRole("navigation", { name: /primary/i })).toHaveCount(0);

    // Reload — state survives.
    await page.reload();
    await expect(page.getByRole("navigation", { name: /primary/i })).toHaveCount(0);

    // Restore the expanded state for the rest of the suite.
    await page.getByRole("button", { name: /mostrar menú lateral/i }).click();
    await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();
  });

  test("notification bell opens the panel and Escape closes it @smoke", async ({ page }) => {
    await page.getByRole("button", { name: /notificaciones/i }).click();
    await expect(page.getByTestId("notification-panel")).toBeVisible();
    await expect(page.getByRole("heading", { name: /notificaciones/i })).toBeVisible();
    await expect(page.getByText(/2 nuevas/)).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("notification-panel")).toHaveCount(0);
  });
});
