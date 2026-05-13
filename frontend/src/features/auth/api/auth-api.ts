import { api } from "@/lib/api/client";

import type { AuthUser } from "../types";

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
};

export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>("/api/v1/auth/login", { email, password });
    return response.data;
  },
  refresh: async (refreshToken: string): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>("/api/v1/auth/refresh", {
      refresh_token: refreshToken,
    });
    return response.data;
  },
  logout: async (refreshToken: string): Promise<void> => {
    await api.post("/api/v1/auth/logout", { refresh_token: refreshToken });
  },
  requestPasswordRecovery: async (email: string): Promise<void> => {
    await api.post("/api/v1/auth/password-recovery", { email });
  },
  resetPassword: async (token: string, newPassword: string): Promise<void> => {
    await api.post("/api/v1/auth/password-reset", { token, new_password: newPassword });
  },
  getMe: async (): Promise<AuthUser> => {
    const response = await api.get<AuthUser>("/api/v1/auth/me");
    return response.data;
  },
};
