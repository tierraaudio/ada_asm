import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { NotificationMenu } from "./NotificationMenu";
import { renderWithProviders } from "@/tests/utils";

describe("<NotificationMenu>", () => {
  it("opens the panel on bell click and closes on Escape", async () => {
    renderWithProviders(<NotificationMenu />);
    expect(screen.queryByTestId("notification-panel")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /notificaciones/i }));
    expect(await screen.findByTestId("notification-panel")).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByTestId("notification-panel")).not.toBeInTheDocument());
  });

  it("closes on outside-click", async () => {
    renderWithProviders(
      <div>
        <NotificationMenu />
        <button type="button">outside</button>
      </div>,
    );
    await userEvent.click(screen.getByRole("button", { name: /notificaciones/i }));
    await screen.findByTestId("notification-panel");

    await userEvent.click(screen.getByRole("button", { name: /outside/i }));
    await waitFor(() => expect(screen.queryByTestId("notification-panel")).not.toBeInTheDocument());
  });
});
