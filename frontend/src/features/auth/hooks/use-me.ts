import { useQuery } from "@tanstack/react-query";

import { authApi } from "../api/auth-api";
import type { AuthUser } from "../types";

export const meQueryKey = ["auth", "me"] as const;

export function useMe(enabled: boolean = true) {
  return useQuery<AuthUser>({
    queryKey: meQueryKey,
    queryFn: authApi.getMe,
    enabled,
    staleTime: 60_000,
    retry: false,
  });
}
