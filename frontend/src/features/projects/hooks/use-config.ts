import { useQuery } from "@tanstack/react-query";

import { configApi } from "../api/config-api";

const TEN_MINUTES_MS = 10 * 60 * 1000;

export function configQueryKey() {
  return ["config"] as const;
}

export function useConfig() {
  return useQuery({
    queryKey: configQueryKey(),
    queryFn: () => configApi.get(),
    staleTime: TEN_MINUTES_MS,
  });
}
