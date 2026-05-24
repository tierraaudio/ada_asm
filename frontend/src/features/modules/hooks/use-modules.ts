import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { modulesApi } from "../api/modules-api";
import type { ModuleFilters } from "../types";

export function modulesListQueryKey(filters: ModuleFilters, page: number, pageSize: number) {
  return ["modules", "list", { filters, page, pageSize }] as const;
}

export function useModules(filters: ModuleFilters, page: number, pageSize: number) {
  return useQuery({
    queryKey: modulesListQueryKey(filters, page, pageSize),
    queryFn: () => modulesApi.list(filters, page, pageSize),
    placeholderData: keepPreviousData,
  });
}
