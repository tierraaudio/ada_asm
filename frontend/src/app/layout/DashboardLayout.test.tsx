import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardLayout } from "./DashboardLayout";
import { useUiStore } from "@/lib/stores/ui-store";
import { loginInStore, renderWithProviders } from "@/tests/utils";

describe("<DashboardLayout>", () => {
  it("renders the Sidebar when expanded", () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: false });
    renderWithProviders(<DashboardLayout>content</DashboardLayout>);
    expect(screen.getByTestId("app-sidebar")).toBeInTheDocument();
  });

  it("does NOT render the Sidebar when collapsed", () => {
    loginInStore();
    useUiStore.setState({ sidebarCollapsed: true });
    renderWithProviders(<DashboardLayout>content</DashboardLayout>);
    expect(screen.queryByTestId("app-sidebar")).not.toBeInTheDocument();
  });
});
