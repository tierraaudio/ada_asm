import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { componentsApi } from "../api/components-api";
import type { ComponentFilters } from "../types";

export interface UseComponentsArgs {
  filters: ComponentFilters;
  page: number;
  pageSize: number;
}

export function componentsListQueryKey({ filters, page, pageSize }: UseComponentsArgs) {
  return ["components", "list", { filters, page, pageSize }] as const;
}

export function useComponents({ filters, page, pageSize }: UseComponentsArgs) {
  return useQuery({
    queryKey: componentsListQueryKey({ filters, page, pageSize }),
    queryFn: () => componentsApi.list(filters, page, pageSize),
    placeholderData: keepPreviousData,
  });
}
