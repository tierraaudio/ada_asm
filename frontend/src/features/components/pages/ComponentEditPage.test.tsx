import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";
import { loginInStore, renderWithProviders } from "@/tests/utils";

import { ComponentEditPage } from "./ComponentEditPage";

const API = "http://localhost:8000";

const SAMPLE = {
  id: "00000000-0000-0000-0000-000000000abc",
  mpn: "ACS712",
  sku: "ACS712-30A",
  name: "Sensor Hall",
  family: "Sensores",
  description: "",
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

describe("<ComponentEditPage> in create mode", () => {
  it("submits a valid payload and navigates to the new detail page", async () => {
    loginInStore();
    let captured: unknown = null;
    server.use(
      http.post(`${API}/api/v1/components`, async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({ ...SAMPLE, id: "new-id" }, { status: 201 });
      }),
    );

    renderWithProviders(
      <Routes>
        <Route path="/components/new" element={<ComponentEditPage mode="create" />} />
        <Route path="/components/:id" element={<p>landed-on-detail</p>} />
      </Routes>,
      { route: "/components/new" },
    );

    await userEvent.type(screen.getByLabelText(/^MPN/), "TEST-001");
    await userEvent.type(screen.getByLabelText(/^Nombre/), "Test name");
    await userEvent.type(screen.getByLabelText(/^Familia/), "Sensores");
    await userEvent.click(
      screen.getByRole("button", { name: /crear componente/i }),
    );

    expect(await screen.findByText("landed-on-detail")).toBeInTheDocument();
    expect(captured).toMatchObject({
      mpn: "TEST-001",
      name: "Test name",
      family: "Sensores",
    });
  });

  it("surfaces 409 MPN_ALREADY_REGISTERED as an inline MPN error", async () => {
    loginInStore();
    server.use(
      http.post(`${API}/api/v1/components`, () =>
        HttpResponse.json(
          { code: "MPN_ALREADY_REGISTERED", title: "Conflict", status: 409 },
          { status: 409 },
        ),
      ),
    );

    renderWithProviders(<ComponentEditPage mode="create" />, {
      route: "/components/new",
    });
    await userEvent.type(screen.getByLabelText(/^MPN/), "DUPLICATE");
    await userEvent.type(screen.getByLabelText(/^Nombre/), "Test");
    await userEvent.type(screen.getByLabelText(/^Familia/), "Sensores");
    await userEvent.click(
      screen.getByRole("button", { name: /crear componente/i }),
    );

    expect(
      await screen.findByText(/ya existe un componente con ese MPN/i),
    ).toBeInTheDocument();
  });
});

describe("<ComponentEditPage> in edit mode", () => {
  it("renders MPN as read-only and pre-fills the form", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
    );

    renderWithProviders(
      <Routes>
        <Route
          path="/components/:id/edit"
          element={<ComponentEditPage mode="edit" />}
        />
      </Routes>,
      { route: `/components/${SAMPLE.id}/edit` },
    );

    const mpnField = (await screen.findByLabelText(/^MPN/)) as HTMLInputElement;
    expect(mpnField).toHaveValue("ACS712");
    expect(mpnField).toHaveAttribute("readOnly");
    await waitFor(() =>
      expect(
        (screen.getByLabelText(/^Nombre/) as HTMLInputElement).value,
      ).toBe("Sensor Hall"),
    );
  });

  it("PATCHes and navigates back to detail on save", async () => {
    loginInStore();
    let patched = false;
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
      http.patch(`${API}/api/v1/components/:id`, async () => {
        patched = true;
        return HttpResponse.json({ ...SAMPLE, name: "Renamed" });
      }),
    );

    renderWithProviders(
      <Routes>
        <Route
          path="/components/:id/edit"
          element={<ComponentEditPage mode="edit" />}
        />
        <Route path="/components/:id" element={<p>landed-on-detail</p>} />
      </Routes>,
      { route: `/components/${SAMPLE.id}/edit` },
    );

    await screen.findByLabelText(/^MPN/);
    const name = screen.getByLabelText(/^Nombre/) as HTMLInputElement;
    await userEvent.clear(name);
    await userEvent.type(name, "Renamed");
    await userEvent.click(
      screen.getByRole("button", { name: /guardar cambios/i }),
    );
    expect(await screen.findByText("landed-on-detail")).toBeInTheDocument();
    expect(patched).toBe(true);
  });
});
