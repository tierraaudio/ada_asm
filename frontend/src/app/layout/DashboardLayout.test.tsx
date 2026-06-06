import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardLayout } from "./DashboardLayout";
import { useUiStore } from "@/lib/stores/ui-store";
import { loginInStore, renderWithProviders } from "@/tests/utils";

describe("<DashboardLayout>", () => {
  it("always renders the Sidebar — collapsed it becomes a slim rail with the toggle", () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<DashboardLayout>content</DashboardLayout>);
    expect(screen.getByTestId("app-sidebar")).toBeInTheDocument();
  });

  it("Sidebar stays mounted when collapsed (owns its own toggle)", () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: true });
    renderWithProviders(<DashboardLayout>content</DashboardLayout>);
    expect(screen.getByTestId("app-sidebar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /expandir menú/i })).toBeInTheDocument();
  });
});
