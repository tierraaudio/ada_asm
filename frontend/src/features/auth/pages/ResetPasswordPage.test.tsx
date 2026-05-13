import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResetPasswordPage } from "./ResetPasswordPage";
import { renderWithProviders } from "@/tests/utils";

describe("<ResetPasswordPage>", () => {
  it("shows an error state when no token is in the URL", () => {
    renderWithProviders(<ResetPasswordPage />, { route: "/reset-password" });
    expect(screen.getByText(/enlace de recuperación no es válido/i)).toBeInTheDocument();
  });

  it("renders the form when ?token= is present", () => {
    renderWithProviders(<ResetPasswordPage />, { route: "/reset-password?token=abc123" });
    expect(screen.getByLabelText(/^Nueva contraseña$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Confirmar contraseña/i)).toBeInTheDocument();
  });
});
