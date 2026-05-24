import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  componentsApi,
  type ComponentCreatePayload,
  type ComponentUpdatePayload,
} from "../api/components-api";

export function useDeleteComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => componentsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
    },
  });
}

export function useCreateComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ComponentCreatePayload) => componentsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
    },
  });
}

export function useUpdateComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ComponentUpdatePayload }) =>
      componentsApi.update(id, payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
      qc.invalidateQueries({ queryKey: ["components", "detail", data.id] });
    },
  });
}
