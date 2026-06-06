import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Sidebar } from "./Sidebar";
import { useUiStore } from "@/lib/stores/ui-store";
import { renderWithProviders } from "@/tests/utils";

describe("<Sidebar>", () => {
  it("renders the brand logo image when expanded", () => {
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<Sidebar />);
    const logo = screen.getByAltText(/singular things/i) as HTMLImageElement;
    expect(logo.src).toMatch(/\/brand\/singularthings-wordmark\.svg$/);
  });

  it("renders the three nav items in hierarchy order", () => {
    useUiStore.setState({ sidebarCollapsed: false });
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
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<Sidebar />, { route: "/modules" });
    const activeLink = screen.getByRole("link", { name: /módulos/i });
    expect(activeLink.className).toMatch(/bg-text-primary/);
    expect(activeLink.className).toMatch(/text-white/);
  });

  it("exposes a Plegar menú toggle next to the brand logo when expanded", () => {
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<Sidebar />);
    expect(screen.getByRole("button", { name: /plegar menú/i })).toBeInTheDocument();
  });

  it("collapsed state hides labels and surfaces an Expandir menú toggle", () => {
    useUiStore.setState({ sidebarCollapsed: true });
    renderWithProviders(<Sidebar />);
    expect(screen.queryByAltText(/singular things/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /expandir menú/i })).toBeInTheDocument();
  });

  it("clicking the toggle flips the store value", async () => {
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<Sidebar />);
    await userEvent.click(screen.getByRole("button", { name: /plegar menú/i }));
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
  });
});
