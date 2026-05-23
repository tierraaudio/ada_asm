import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { componentsApi } from "../api/components-api";

export function componentPurchasesQueryKey(
  id: string,
  page: number,
  pageSize: number,
) {
  return ["components", "purchases", id, { page, pageSize }] as const;
}

export function useComponentPurchases(
  id: string | undefined,
  page = 1,
  pageSize = 25,
) {
  return useQuery({
    queryKey: componentPurchasesQueryKey(id ?? "", page, pageSize),
    queryFn: () => componentsApi.listPurchases(id as string, page, pageSize),
    enabled: Boolean(id),
    placeholderData: keepPreviousData,
  });
}
