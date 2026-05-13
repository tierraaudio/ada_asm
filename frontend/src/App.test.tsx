import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { loginInStore, renderWithProviders, sampleUser } from "@/tests/utils";

describe("App", () => {
  it("redirects anonymous users from / to /login", () => {
    renderWithProviders(<App />, { route: "/" });
    // The login page exposes the form heading "ASM V2".
    expect(screen.getByText(/^ASM V2$/)).toBeInTheDocument();
  });

  it("renders the placeholder shell when authenticated", () => {
    loginInStore(sampleUser);
    renderWithProviders(<App />, { route: "/" });
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /primary/i })).toBeInTheDocument();
    expect(screen.getByText(/ada asm placeholder/i)).toBeInTheDocument();
  });
});
