import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { server } from "@/tests/setup";
import { renderWithProviders } from "@/tests/utils";

const API = "http://localhost:8000";

describe("<ForgotPasswordPage>", () => {
  it("shows the neutral confirmation regardless of API response", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/password-recovery`, () =>
        HttpResponse.json({ status: "accepted" }, { status: 202 }),
      ),
    );

    renderWithProviders(<ForgotPasswordPage />, { route: "/forgot-password" });
    await userEvent.type(screen.getByLabelText(/email/i), "anyone@example.com");
    await userEvent.click(screen.getByRole("button", { name: /enviar enlace/i }));

    await waitFor(() => {
      expect(screen.getByText(/Si existe una cuenta/i)).toBeInTheDocument();
    });
  });

  it("shows the same confirmation when the API errors", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/password-recovery`, () => HttpResponse.error()),
    );

    renderWithProviders(<ForgotPasswordPage />, { route: "/forgot-password" });
    await userEvent.type(screen.getByLabelText(/email/i), "anyone@example.com");
    await userEvent.click(screen.getByRole("button", { name: /enviar enlace/i }));

    await waitFor(() => {
      expect(screen.getByText(/Si existe una cuenta/i)).toBeInTheDocument();
    });
  });
});
