import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { customersApi, type CustomerCreatePayload } from "../api/customers-api";

export function customersListQueryKey() {
  return ["customers", "list"] as const;
}

export function useCustomers() {
  return useQuery({
    queryKey: customersListQueryKey(),
    queryFn: () => customersApi.list(),
  });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CustomerCreatePayload) => customersApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: customersListQueryKey() });
    },
  });
}
