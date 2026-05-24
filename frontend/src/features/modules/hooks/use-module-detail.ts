import { useQuery } from "@tanstack/react-query";

import { modulesApi } from "../api/modules-api";

export function moduleDetailQueryKey(id: string) {
  return ["modules", "detail", id] as const;
}

export function useModuleDetail(id: string | undefined) {
  return useQuery({
    queryKey: moduleDetailQueryKey(id ?? ""),
    queryFn: () => modulesApi.get(id as string),
    enabled: Boolean(id),
  });
}
