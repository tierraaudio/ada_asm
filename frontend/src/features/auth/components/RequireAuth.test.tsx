import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";

import { RequireAuth } from "./RequireAuth";
import { loginInStore, renderWithProviders } from "@/tests/utils";

const Protected = () => <p>protected content</p>;
const Login = () => <p>login page</p>;

function renderApp(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<Protected />} />
      </Route>
    </Routes>,
    { route },
  );
}

describe("<RequireAuth>", () => {
  it("redirects anonymous to /login with ?next", () => {
    renderApp("/");
    expect(screen.getByText(/login page/i)).toBeInTheDocument();
  });

  it("renders the outlet when authenticated", () => {
    loginInStore();
    renderApp("/");
    expect(screen.getByText(/protected content/i)).toBeInTheDocument();
  });
});
