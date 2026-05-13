import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import type { AuthUser } from "@/features/auth/types";
import { useAuthStore } from "@/lib/stores/auth-store";

export function renderWithProviders(ui: ReactElement, options?: { route?: string }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[options?.route ?? "/"]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

export const sampleUser: AuthUser = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "admin@example.com",
  full_name: "Admin User",
  global_role: "admin",
  is_active: true,
  created_at: "2026-05-13T08:00:00Z",
};

export function loginInStore(user: AuthUser = sampleUser, token = "fake-access-token"): void {
  useAuthStore.setState({ accessToken: token, user, status: "authenticated" });
}
