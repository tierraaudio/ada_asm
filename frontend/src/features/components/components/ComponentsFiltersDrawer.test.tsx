import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/tests/utils";

import type { Supplier } from "../types";
import { ComponentsFiltersDrawer } from "./ComponentsFiltersDrawer";

const SUPPLIERS: Supplier[] = [
  { id: "sup-1", name: "DigiKey" },
  { id: "sup-2", name: "Mouser" },
];

describe("<ComponentsFiltersDrawer>", () => {
  it("opens, lets the user toggle chips and commits on Aplicar", async () => {
    const onApply = vi.fn();
    renderWithProviders(
      <ComponentsFiltersDrawer
        value={{}}
        onApply={onApply}
        onClear={vi.fn()}
        familyOptions={["Sensores", "Microcontroladores"]}
        suppliers={SUPPLIERS}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /Abrir filtros/i }));
    await userEvent.click(await screen.findByRole("button", { name: "Sensores" }));
    await userEvent.click(screen.getByRole("button", { name: "Tier 1" }));
    await userEvent.click(screen.getByRole("button", { name: "A+" }));
    await userEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledWith({
      families: ["Sensores"],
      tiers: [1],
      nato_scores: ["A+"],
    });
  });

  it("invokes onClear when 'Limpiar filtros' is clicked", async () => {
    const onClear = vi.fn();
    renderWithProviders(
      <ComponentsFiltersDrawer
        value={{ families: ["Sensores"] }}
        onApply={vi.fn()}
        onClear={onClear}
        familyOptions={["Sensores"]}
        suppliers={SUPPLIERS}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /Abrir filtros/i }));
    await userEvent.click(await screen.findByRole("button", { name: /Limpiar filtros/i }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("shows a count badge with the number of active filters", () => {
    renderWithProviders(
      <ComponentsFiltersDrawer
        value={{ families: ["A", "B"], tiers: [1] }}
        onApply={vi.fn()}
        onClear={vi.fn()}
        familyOptions={["A", "B"]}
        suppliers={SUPPLIERS}
      />,
    );
    // The badge sits inside the trigger button labelled "Abrir filtros".
    const trigger = screen.getByRole("button", { name: /Abrir filtros/i });
    expect(trigger).toHaveTextContent("3");
  });
});
