import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  modulesApi,
  type AddChildPayload,
  type ModuleCreatePayload,
  type ModuleUpdatePayload,
  type UpdateChildPayload,
} from "../api/modules-api";

export function useCreateModule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ModuleCreatePayload) => modulesApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["modules", "list"] });
    },
  });
}

export function useUpdateModule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ModuleUpdatePayload }) =>
      modulesApi.update(id, payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["modules", "list"] });
      qc.invalidateQueries({ queryKey: ["modules", "detail", data.id] });
    },
  });
}

export function useDeleteModule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => modulesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["modules", "list"] });
    },
  });
}

export function useAddChild() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AddChildPayload }) =>
      modulesApi.addChild(id, payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["modules", "detail", vars.id] });
      qc.invalidateQueries({ queryKey: ["modules", "list"] });
    },
  });
}

export function useUpdateChild() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      childId,
      payload,
    }: {
      id: string;
      childId: string;
      payload: UpdateChildPayload;
    }) => modulesApi.updateChild(id, childId, payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["modules", "detail", vars.id] });
    },
  });
}

export function useRemoveChild() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, childId }: { id: string; childId: string }) =>
      modulesApi.removeChild(id, childId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["modules", "detail", vars.id] });
      qc.invalidateQueries({ queryKey: ["modules", "list"] });
    },
  });
}
