import { useQuery } from "@tanstack/react-query";

import { modulesApi } from "../api/modules-api";

export function modulePriceHistoryQueryKey(id: string, period: "week" | "month" | "year") {
  return ["modules", "price-history", id, period] as const;
}

export function useModulePriceHistory(
  id: string | undefined,
  period: "week" | "month" | "year",
  enabled = true,
) {
  return useQuery({
    queryKey: modulePriceHistoryQueryKey(id ?? "", period),
    queryFn: () => modulesApi.listPriceHistory(id as string, period),
    enabled: Boolean(id) && enabled,
  });
}
