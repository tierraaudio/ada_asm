import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { UserMenuPill } from "./UserMenuPill";
import { useAuthStore } from "@/lib/stores/auth-store";
import { server } from "@/tests/setup";
import { loginInStore, renderWithProviders, sampleUser } from "@/tests/utils";

const API = "http://localhost:8000";

describe("<UserMenuPill>", () => {
  it("renders the user's full name and role", () => {
    loginInStore();
    renderWithProviders(<UserMenuPill />);
    expect(screen.getByText(sampleUser.full_name)).toBeInTheDocument();
    expect(screen.getByText(/administrator/i)).toBeInTheDocument();
  });

  it("opens the dropdown on click and shows email + logout action", async () => {
    loginInStore();
    renderWithProviders(<UserMenuPill />);
    await userEvent.click(screen.getByRole("button", { name: /menú de usuario/i }));
    expect(await screen.findByText(sampleUser.email)).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /cerrar sesión/i })).toBeInTheDocument();
  });

  it("logging out calls the API, clears state and routes to /login", async () => {
    loginInStore(sampleUser, "access-xyz");
    localStorage.setItem("adaasm.auth.refreshToken", "refresh-xyz");
    let logoutCalled = false;
    server.use(
      http.post(`${API}/api/v1/auth/logout`, () => {
        logoutCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<UserMenuPill />);
    await userEvent.click(screen.getByRole("button", { name: /menú de usuario/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: /cerrar sesión/i }));

    await waitFor(() => {
      expect(useAuthStore.getState().status).toBe("anonymous");
    });
    expect(localStorage.getItem("adaasm.auth.refreshToken")).toBeNull();
    expect(logoutCalled).toBe(true);
  });

  it("logout still clears local state when the backend call errors", async () => {
    loginInStore(sampleUser, "access-xyz");
    localStorage.setItem("adaasm.auth.refreshToken", "refresh-xyz");
    server.use(http.post(`${API}/api/v1/auth/logout`, () => HttpResponse.error()));

    renderWithProviders(<UserMenuPill />);
    await userEvent.click(screen.getByRole("button", { name: /menú de usuario/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: /cerrar sesión/i }));

    await waitFor(() => {
      expect(useAuthStore.getState().status).toBe("anonymous");
    });
    expect(localStorage.getItem("adaasm.auth.refreshToken")).toBeNull();
  });
});
