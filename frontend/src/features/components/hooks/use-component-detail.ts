import { useQuery } from "@tanstack/react-query";

import { componentsApi } from "../api/components-api";

export function componentDetailQueryKey(id: string) {
  return ["components", "detail", id] as const;
}

export function useComponentDetail(id: string | undefined) {
  return useQuery({
    queryKey: componentDetailQueryKey(id ?? ""),
    queryFn: () => componentsApi.get(id as string),
    enabled: Boolean(id),
  });
}
