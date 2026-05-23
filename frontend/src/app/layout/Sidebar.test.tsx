import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sidebar } from "./Sidebar";
import { renderWithProviders } from "@/tests/utils";

describe("<Sidebar>", () => {
  it("renders the brand logo image", () => {
    renderWithProviders(<Sidebar />);
    const logo = screen.getByAltText(/singular things/i) as HTMLImageElement;
    expect(logo.src).toMatch(/\/brand\/singularthings-wordmark\.svg$/);
  });

  it("renders the three nav items in hierarchy order", () => {
    renderWithProviders(<Sidebar />);
    const nav = screen.getByRole("navigation", { name: /primary/i });
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.textContent?.trim())).toEqual([
      "Proyectos",
      "Módulos",
      "Componentes",
    ]);
    expect(links[0]).toHaveAttribute("href", "/projects");
    expect(links[1]).toHaveAttribute("href", "/modules");
    expect(links[2]).toHaveAttribute("href", "/components");
  });

  it("highlights the active route", () => {
    renderWithProviders(<Sidebar />, { route: "/modules" });
    const activeLink = screen.getByRole("link", { name: /módulos/i });
    expect(activeLink.className).toMatch(/bg-text-primary/);
    expect(activeLink.className).toMatch(/text-white/);
  });
});
