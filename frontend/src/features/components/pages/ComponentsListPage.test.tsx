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
    expect(screen.getByLabelText(/Scoring OTAN A\+/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ver componente/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Eliminar componente/i })).toBeInTheDocument();
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

  it("opens the delete confirmation dialog when the trash button is clicked", async () => {
    loginInStore();
    stubEndpoints();
    renderWithProviders(<ComponentsListPage />, { route: "/components" });

    await screen.findByText("MCU-001");
    await userEvent.click(screen.getByRole("button", { name: /Eliminar componente/i }));
    expect(await screen.findByText("¿Eliminar componente?")).toBeInTheDocument();
  });
});
