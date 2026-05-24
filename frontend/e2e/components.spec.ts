import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@singularthings.io";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "admin123";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
  await page.getByLabel(/contraseña/i).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /iniciar sesión/i }).click();
  await expect(page).toHaveURL("/");
}

test.describe("Components catalogue @smoke", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("list → detail → historial → editar end-to-end @smoke", async ({ page }) => {
    await page.goto("/components");
    await expect(page.getByRole("heading", { name: "Componentes" })).toBeVisible();

    // The seed script (`seed_components`) inserts ACS712 amongst the catalogue.
    const acsRow = page.getByRole("row").filter({ hasText: "ACS712" }).first();
    await expect(acsRow).toBeVisible();
    await acsRow.click();

    await expect(page).toHaveURL(/\/components\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: "ACS712" })).toBeVisible();

    // Click the "Historial" tab → land on the purchases route.
    await page.getByRole("tab", { name: "Historial" }).click();
    await expect(page).toHaveURL(/\/components\/[0-9a-f-]{36}\/purchases$/);
    await expect(page.getByRole("heading", { name: "ACS712" })).toBeVisible();

    // Editar → form.
    await page.goto(page.url().replace("/purchases", "/edit"));
    await expect(page.getByRole("heading", { name: /Editar ACS712/ })).toBeVisible();
    const nameInput = page.getByLabel(/^Nombre/);
    await nameInput.fill("ACS712 — editado E2E");
    await page.getByRole("button", { name: /guardar cambios/i }).click();

    await expect(page).toHaveURL(/\/components\/[0-9a-f-]{36}$/);
    await expect(page.getByText(/ACS712 — editado E2E/)).toBeVisible();
  });

  test("create a brand-new component @smoke", async ({ page }) => {
    await page.goto("/components");
    await page.getByRole("button", { name: /nuevo componente/i }).click();
    await expect(page).toHaveURL("/components/new");

    const mpn = `E2E-${Date.now()}`;
    await page.getByLabel(/^MPN/).fill(mpn);
    await page.getByLabel(/^Nombre/).fill("Componente E2E");
    await page.getByLabel(/^Familia/).fill("Sensores");
    await page.getByRole("button", { name: /crear componente/i }).click();

    await expect(page).toHaveURL(/\/components\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: mpn })).toBeVisible();
    await expect(page.getByText("Componente E2E")).toBeVisible();
  });
});
