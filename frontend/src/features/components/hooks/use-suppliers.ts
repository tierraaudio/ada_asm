import { useQuery } from "@tanstack/react-query";

import { suppliersApi } from "../api/components-api";

export function suppliersQueryKey() {
  return ["suppliers", "list"] as const;
}

export function useSuppliers() {
  return useQuery({
    queryKey: suppliersQueryKey(),
    queryFn: () => suppliersApi.list(),
    staleTime: 5 * 60 * 1000,
  });
}
