import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";
import { loginInStore, renderWithProviders } from "@/tests/utils";

import { ComponentsListPage } from "./ComponentsListPage";

const API = "http://localhost:8000";

const SAMPLE_ROW = {
  id: "00000000-0000-0000-0000-000000000abc",
  mpn: "ACS712",
  sku: "ACS712-30A",
  name: "Sensor corriente Hall",
  family: "Sensores",
  description: null,
  datasheet_url: null,
  location: "A-12-3",
  supplier: "DigiKey",
  price_per_100: "8.4500",
  stock: 145,
  tier: "B" as const,
  nato_score: "otan" as const,
  country_of_origin: "US",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

describe("<ComponentsListPage>", () => {
  it("renders rows returned by the API", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components`, () =>
        HttpResponse.json({
          items: [SAMPLE_ROW],
          total: 1,
          page: 1,
          page_size: 25,
        }),
      ),
    );

    renderWithProviders(<ComponentsListPage />, { route: "/components" });

    expect(
      await screen.findByText("Sensor corriente Hall"),
    ).toBeInTheDocument();
    expect(screen.getByText("ACS712")).toBeInTheDocument();
    expect(screen.getByLabelText(/Tier B/)).toBeInTheDocument();
  });

  it("shows the empty state when total is 0", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components`, () =>
        HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 }),
      ),
    );

    renderWithProviders(<ComponentsListPage />, { route: "/components" });

    expect(
      await screen.findByText("Aún no hay componentes"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /crea el primero/i })).toBeInTheDocument();
  });

  it("debounces the search input and forwards q to the API", async () => {
    loginInStore();
    let capturedQ: string | null | undefined;
    server.use(
      http.get(`${API}/api/v1/components`, ({ request }) => {
        capturedQ = new URL(request.url).searchParams.get("q");
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
    );

    renderWithProviders(<ComponentsListPage />, { route: "/components" });
    await screen.findByText("Aún no hay componentes");

    await userEvent.type(
      screen.getByLabelText(/buscar componentes/i),
      "esp32",
    );
    await waitFor(() => expect(capturedQ).toBe("esp32"), { timeout: 1500 });
  });

  it("forwards the selected filter dropdown choice to the API as a query param", async () => {
    loginInStore();
    const capturedParams: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/api/v1/components`, ({ request }) => {
        capturedParams.push(new URL(request.url).searchParams);
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
    );

    renderWithProviders(<ComponentsListPage />, { route: "/components" });
    await screen.findByText("Aún no hay componentes");

    await userEvent.click(screen.getByRole("button", { name: /Familia:/ }));
    await userEvent.click(screen.getByText("Sensores"));

    await waitFor(() =>
      expect(
        capturedParams.some((p) => p.get("family") === "Sensores"),
      ).toBe(true),
    );
  });

  it("opens the confirm dialog when the row 'Eliminar' action is selected", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components`, () =>
        HttpResponse.json({
          items: [SAMPLE_ROW],
          total: 1,
          page: 1,
          page_size: 25,
        }),
      ),
    );

    renderWithProviders(<ComponentsListPage />, { route: "/components" });

    await screen.findByText("Sensor corriente Hall");
    await userEvent.click(
      screen.getByRole("button", { name: /acciones del componente/i }),
    );
    await userEvent.click(screen.getByText("Eliminar"));

    expect(
      await screen.findByText("¿Eliminar componente?"),
    ).toBeInTheDocument();
  });
});
