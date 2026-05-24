import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";
import { useAuthStore } from "@/lib/stores/auth-store";
import { server } from "@/tests/setup";
import { renderWithProviders, sampleUser } from "@/tests/utils";

const API = "http://localhost:8000";

describe("<LoginPage>", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENV", "development");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("logs in on valid credentials and populates the store", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/login`, () =>
        HttpResponse.json({
          access_token: "access-xyz",
          refresh_token: "refresh-xyz",
          token_type: "bearer",
          expires_in: 900,
        }),
      ),
      http.get(`${API}/api/v1/auth/me`, () => HttpResponse.json(sampleUser)),
    );

    renderWithProviders(<LoginPage />, { route: "/login" });
    await userEvent.type(screen.getByLabelText(/email/i), "admin@example.com");
    await userEvent.type(screen.getByLabelText(/contraseña/i), "long-enough-passphrase");
    await userEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await waitFor(() => {
      expect(useAuthStore.getState().status).toBe("authenticated");
    });
    expect(useAuthStore.getState().accessToken).toBe("access-xyz");
    expect(useAuthStore.getState().user).toEqual(sampleUser);
    expect(localStorage.getItem("adaasm.auth.refreshToken")).toBe("refresh-xyz");
  });

  it("shows an inline error on 401 and clears the password field", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/login`, () =>
        HttpResponse.json(
          { code: "INVALID_CREDENTIALS", title: "Invalid Credentials" },
          { status: 401 },
        ),
      ),
    );

    renderWithProviders(<LoginPage />, { route: "/login" });
    await userEvent.type(screen.getByLabelText(/email/i), "admin@example.com");
    const password = screen.getByLabelText(/contraseña/i) as HTMLInputElement;
    await userEvent.type(password, "wrong-pass");
    await userEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/email o la contraseña/i);
    expect(password.value).toBe("");
  });

  it("renders the development credentials chip when VITE_ENV=development", () => {
    renderWithProviders(<LoginPage />, { route: "/login" });
    expect(screen.getByText(/Usuarios de prueba/i)).toBeInTheDocument();
    expect(screen.getByText(/admin@singularthings\.io \/ admin123/)).toBeInTheDocument();
  });
});
