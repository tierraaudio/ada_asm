import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Header } from "./Header";
import { useUiStore } from "@/lib/stores/ui-store";
import { loginInStore, renderWithProviders } from "@/tests/utils";

describe("<Header>", () => {
  it("renders Menu icon when sidebar is collapsed", () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: true });
    renderWithProviders(<Header />);
    expect(screen.getByRole("button", { name: /mostrar menú lateral/i })).toBeInTheDocument();
  });

  it("renders X icon when sidebar is expanded", () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<Header />);
    expect(screen.getByRole("button", { name: /ocultar menú lateral/i })).toBeInTheDocument();
  });

  it("clicking the toggle flips the store value", async () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<Header />);
    await userEvent.click(screen.getByRole("button", { name: /ocultar menú lateral/i }));
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
  });

  it("renders the sidebar toggle, bell and user menu pill", () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<Header />);
    expect(screen.getByRole("button", { name: /ocultar menú lateral/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /notificaciones/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /admin user/i })).toBeInTheDocument();
  });
});
