import { useQuery } from "@tanstack/react-query";

import { componentsApi } from "../api/components-api";

export function componentParentsQueryKey(id: string) {
  return ["components", "parents", id] as const;
}

export function useComponentParents(id: string | undefined) {
  return useQuery({
    queryKey: componentParentsQueryKey(id ?? ""),
    queryFn: () => componentsApi.listParents(id as string),
    enabled: Boolean(id),
  });
}
