import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { computeStockStatus, StockStatusBadge } from "./StockStatusBadge";

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

  it("returns 'warning' when stock = 0 but supplier has stock", () => {
    expect(computeStockStatus(0, 5, [{ supplier: "DigiKey", quantity: 100 }])).toBe("warning");
  });
});

describe("<StockStatusBadge>", () => {
  it("renders the number of units", () => {
    render(<StockStatusBadge stock={145} stockMin={5} />);
    expect(screen.getByText("145 uds")).toBeInTheDocument();
  });

  it("shows the hover popover with supplier detail on 'warning'", async () => {
    render(
      <StockStatusBadge
        stock={3}
        stockMin={10}
        supplierStock={[{ supplier: "DigiKey", quantity: 240 }]}
      />,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(await screen.findByText("Detalle de alertas:")).toBeInTheDocument();
    expect(screen.getByText(/DigiKey: 240 uds disponibles/)).toBeInTheDocument();
  });

  it("shows 'sin stock' lines on 'critical'", async () => {
    render(<StockStatusBadge stock={0} stockMin={5} />);
    await userEvent.click(screen.getByRole("button"));
    expect(await screen.findByText("Detalle de alertas:")).toBeInTheDocument();
    expect(screen.getByText(/Sin stock interno/)).toBeInTheDocument();
    expect(screen.getByText(/Sin disponibilidad en proveedores de confianza/)).toBeInTheDocument();
  });

  it("does not render a popover trigger on 'ok'", () => {
    render(<StockStatusBadge stock={100} stockMin={5} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
