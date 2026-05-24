import { act, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/tests/utils";

import { computeStockStatus, StockStatusBadge } from "./StockStatusBadge";

async function focusBadge(label: RegExp) {
  // jsdom doesn't fire pointer events reliably for Radix Tooltip; focus opens
  // the same tooltip with the same content.
  await act(async () => {
    screen.getByLabelText(label).focus();
  });
}

describe("computeStockStatus", () => {
  it("returns 'ok' when stock >= stockMin", () => {
    expect(computeStockStatus(10, 5, [])).toBe("ok");
    expect(computeStockStatus(5, 5, [])).toBe("ok");
  });

  it("returns 'warning' when stock < stockMin and some supplier has stock", () => {
    expect(computeStockStatus(3, 5, [{ supplier: "DigiKey", quantity: 100 }])).toBe("warning");
  });

  it("returns 'warning' when stock > 0 even without supplier info", () => {
    expect(computeStockStatus(3, 5, [])).toBe("warning");
  });

  it("returns 'critical' when stock = 0 and no supplier has stock", () => {
    expect(computeStockStatus(0, 5, [{ supplier: "DigiKey", quantity: 0 }])).toBe("critical");
    expect(computeStockStatus(0, 5, [])).toBe("critical");
  });

  it("returns 'warning' when stock = 0 but some supplier has stock", () => {
    expect(computeStockStatus(0, 5, [{ supplier: "DigiKey", quantity: 100 }])).toBe("warning");
  });
});

describe("<StockStatusBadge>", () => {
  it("renders the number of units", () => {
    renderWithProviders(<StockStatusBadge stock={145} stockMin={5} />);
    expect(screen.getByText("145 uds")).toBeInTheDocument();
  });

  it("shows the warning tooltip with supplier detail on focus", async () => {
    renderWithProviders(
      <StockStatusBadge
        stock={3}
        stockMin={10}
        supplierStock={[{ supplier: "DigiKey", quantity: 240 }]}
      />,
    );
    await focusBadge(/Stock: 3 uds \(warning\)/);
    // Radix renders the tooltip content twice (visible + visually-hidden
    // for screen readers); both copies match — assert >= 1.
    expect((await screen.findAllByText("Detalle de alertas:")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/DigiKey: 240 uds disponibles/).length).toBeGreaterThan(0);
  });

  it("shows the critical tooltip on focus when stock=0 and suppliers empty", async () => {
    renderWithProviders(<StockStatusBadge stock={0} stockMin={5} />);
    await focusBadge(/Stock: 0 uds \(critical\)/);
    expect((await screen.findAllByText("Detalle de alertas:")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Sin stock interno/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Sin disponibilidad en proveedores de confianza/).length,
    ).toBeGreaterThan(0);
  });

  it("shows the ok tooltip when stock is sufficient", async () => {
    renderWithProviders(<StockStatusBadge stock={100} stockMin={5} />);
    await focusBadge(/Stock: 100 uds \(ok\)/);
    expect((await screen.findAllByText("Stock suficiente")).length).toBeGreaterThan(0);
  });
});
