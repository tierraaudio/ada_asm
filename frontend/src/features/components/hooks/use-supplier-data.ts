import { useQuery } from "@tanstack/react-query";

import { componentsApi } from "../api/components-api";

export function supplierPricesQueryKey(componentId: string) {
  return ["components", "supplier-prices", componentId] as const;
}

export function useSupplierPrices(componentId: string | undefined) {
  return useQuery({
    queryKey: supplierPricesQueryKey(componentId ?? ""),
    queryFn: () => componentsApi.listSupplierPrices(componentId as string),
    enabled: Boolean(componentId),
  });
}

export function supplierStocksQueryKey(componentId: string) {
  return ["components", "supplier-stocks", componentId] as const;
}

export function useSupplierStocks(componentId: string | undefined) {
  return useQuery({
    queryKey: supplierStocksQueryKey(componentId ?? ""),
    queryFn: () => componentsApi.listSupplierStocks(componentId as string),
    enabled: Boolean(componentId),
  });
}

export function stockEventsQueryKey(componentId: string) {
  return ["components", "stock-events", componentId] as const;
}

export function useStockEvents(componentId: string | undefined) {
  return useQuery({
    queryKey: stockEventsQueryKey(componentId ?? ""),
    queryFn: () => componentsApi.listStockEvents(componentId as string),
    enabled: Boolean(componentId),
  });
}
