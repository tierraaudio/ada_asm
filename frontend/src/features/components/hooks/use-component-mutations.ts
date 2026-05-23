import { useMutation, useQueryClient } from "@tanstack/react-query";

import { componentsApi } from "../api/components-api";
import type {
  ComponentCreatePayload,
  ComponentUpdatePayload,
} from "../schemas";
import type { Component } from "../types";

export function useCreateComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ComponentCreatePayload) => componentsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
    },
  });
}

export function useUpdateComponent(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ComponentUpdatePayload) => componentsApi.update(id, payload),
    onSuccess: (updated: Component) => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
      qc.setQueryData(["components", "detail", id], updated);
    },
  });
}

export function useDeleteComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => componentsApi.delete(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
      qc.removeQueries({ queryKey: ["components", "detail", id] });
      qc.removeQueries({ queryKey: ["components", "purchases", id] });
    },
  });
}

export function useSyncComponent() {
  return useMutation({
    mutationFn: (id: string) => componentsApi.sync(id),
  });
}
