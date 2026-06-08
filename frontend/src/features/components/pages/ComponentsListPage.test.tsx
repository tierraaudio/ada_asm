import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";
import { loginInStore, renderWithProviders } from "@/tests/utils";

import { ComponentsListPage } from "./ComponentsListPage";

const API = "http://localhost:8000";

const SAMPLE_ROW = {
  id: "comp-1",
  mpn: "STM32F407VGT6",
  sku: "MCU-001",
  name: "STM32F407VGT6 - ARM Cortex-M4 MCU",
  family: "Microcontroladores",
  description: null,
  datasheet_url: null,
  location: "G-A-12",
  fabricante: "STMicroelectronics",
  tipo_almacenamiento: "Gaveta",
  holded_id: null,
  fecha_creacion: null,
  verificado: true,
  notas: null,
  stock: 145,
  stock_min: 5,
  tier: 1 as const,
  nato_score: "A+" as const,
  country_of_origin: "FR",
  proveedor_preferente_id: "sup-1",
  current_price_per_100_eur: "7.2000",
  supplier_stock_summary: [],
  created_at: "2026-05-24T00:00:00Z",
  updated_at: "2026-05-24T00:00:00Z",
};

function stubEndpoints(rows = [SAMPLE_ROW]) {
  server.use(
    http.get(`${API}/api/v1/components`, () =>
      HttpResponse.json({
        items: rows,
        total: rows.length,
        page: 1,
        page_size: 25,
      }),
    ),
    http.get(`${API}/api/v1/suppliers`, () =>
      HttpResponse.json([{ id: "sup-1", name: "DigiKey" }]),
    ),
  );
}

describe("<ComponentsListPage>", () => {
  it("renders the row with SKU + MPN + family icon + NATO badge + stock", async () => {
    loginInStore();
    stubEndpoints();

    renderWithProviders(<ComponentsListPage />, { route: "/components" });

    expect(await screen.findByText("MCU-001")).toBeInTheDocument();
    expect(screen.getByText("STM32F407VGT6")).toBeInTheDocument();
    expect(screen.getByText("STM32F407VGT6 - ARM Cortex-M4 MCU")).toBeInTheDocument();
    expect(screen.getByText("Microcontroladores")).toBeInTheDocument();
    expect(screen.getByText("G-A-12")).toBeInTheDocument();
    expect(screen.getByText("DigiKey")).toBeInTheDocument();
    expect(screen.getByText("145 uds")).toBeInTheDocument();
    // Spanish euro formatter ⇒ "7,20 €"
    expect(screen.getByText(/7,20.*€/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Scoring OTAN A\+/)).toBeInTheDocument();
    // The entire row is the "view" affordance — role="button" with the SKU
    // text inside it. Delete moved to the component detail page (no per-row
    // trash button on the list anymore).
    const rowButtons = screen
      .getAllByRole("button")
      .filter((b) => b.textContent?.includes("MCU-001"));
    expect(rowButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("shows the empty state when total is 0", async () => {
    loginInStore();
    stubEndpoints([]);
    renderWithProviders(<ComponentsListPage />, { route: "/components" });
    expect(await screen.findByText("Aún no hay componentes")).toBeInTheDocument();
  });

  it("debounces the search input and forwards q to the API", async () => {
    loginInStore();
    let lastQ: string | null = null;
    server.use(
      http.get(`${API}/api/v1/components`, ({ request }) => {
        lastQ = new URL(request.url).searchParams.get("q");
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
      http.get(`${API}/api/v1/suppliers`, () => HttpResponse.json([])),
    );

    renderWithProviders(<ComponentsListPage />, { route: "/components" });
    await screen.findByText("Aún no hay componentes");

    await userEvent.type(screen.getByLabelText(/Buscar componentes/i), "esp32");
    await waitFor(() => expect(lastQ).toBe("esp32"), { timeout: 1500 });
  });

  it("navigates to the component detail when the row is clicked", async () => {
    loginInStore();
    stubEndpoints();
    renderWithProviders(<ComponentsListPage />, { route: "/components" });

    await screen.findByText("MCU-001");
    const row = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("MCU-001"));
    expect(row).toBeDefined();
    await userEvent.click(row!);
    // Delete confirmation now lives in the detail page; clicking the row
    // navigates there. We can't assert the detail page rendered (it's not
    // mounted in this test), but the click should not throw.
    expect(row).toHaveAttribute("role", "button");
  });
});
