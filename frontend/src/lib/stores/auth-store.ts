import { create } from "zustand";

import type { AuthUser } from "@/features/auth/types";

export type AuthStatus = "anonymous" | "authenticating" | "authenticated";

type AuthState = {
  accessToken: string | null;
  user: AuthUser | null;
  status: AuthStatus;
  setStatus: (status: AuthStatus) => void;
  setSession: (accessToken: string, user: AuthUser) => void;
  clearSession: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  status: "anonymous",
  setStatus: (status) => set({ status }),
  setSession: (accessToken, user) => set({ accessToken, user, status: "authenticated" }),
  clearSession: () => set({ accessToken: null, user: null, status: "anonymous" }),
}));
