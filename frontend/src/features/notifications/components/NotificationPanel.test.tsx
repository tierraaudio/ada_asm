import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NotificationPanel } from "./NotificationPanel";
import { renderWithProviders } from "@/tests/utils";

describe("<NotificationPanel>", () => {
  it("renders the heading and the unread-count pill", () => {
    renderWithProviders(<NotificationPanel />);
    expect(screen.getByRole("heading", { name: /notificaciones/i })).toBeInTheDocument();
    expect(screen.getByText(/2 nuevas/)).toBeInTheDocument();
  });

  it("renders six placeholder items with two marked as unread", () => {
    renderWithProviders(<NotificationPanel />);
    const panel = screen.getByTestId("notification-panel");
    const items = within(panel).getAllByRole("listitem");
    expect(items).toHaveLength(6);

    const unreadIndicators = within(panel).getAllByLabelText(/sin leer/i);
    expect(unreadIndicators).toHaveLength(2);
  });

  it("renders the 'Ver todas las notificaciones' footer link", () => {
    renderWithProviders(<NotificationPanel />);
    const link = screen.getByRole("link", { name: /ver todas las notificaciones/i });
    expect(link).toHaveAttribute("href", "/notifications");
  });
});
