import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Header } from "./Header";
import { loginInStore, renderWithProviders } from "@/tests/utils";

describe("<Header>", () => {
  it("renders the notification bell and the user menu pill", () => {
    loginInStore();
    renderWithProviders(<Header />);
    expect(screen.getByRole("button", { name: /notificaciones/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /admin user/i })).toBeInTheDocument();
  });

  it("no longer owns the sidebar toggle (it moved into <Sidebar>)", () => {
    loginInStore();
    renderWithProviders(<Header />);
    expect(screen.queryByRole("button", { name: /menú lateral/i })).not.toBeInTheDocument();
  });
});
