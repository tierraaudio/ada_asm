import { api } from "@/lib/api/client";

import type { Customer } from "../types";

const BASE = "/api/v1/customers";

export interface CustomerCreatePayload {
  holded_id: string;
  name: string;
  holded_url?: string | null;
  notas?: string | null;
}

export type CustomerUpdatePayload = Partial<CustomerCreatePayload>;

export const customersApi = {
  list: async (): Promise<Customer[]> => {
    const response = await api.get<Customer[]>(BASE);
    return response.data;
  },

  get: async (id: string): Promise<Customer> => {
    const response = await api.get<Customer>(`${BASE}/${id}`);
    return response.data;
  },

  create: async (payload: CustomerCreatePayload): Promise<Customer> => {
    const response = await api.post<Customer>(BASE, payload);
    return response.data;
  },

  update: async (id: string, payload: CustomerUpdatePayload): Promise<Customer> => {
    const response = await api.patch<Customer>(`${BASE}/${id}`, payload);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`${BASE}/${id}`);
  },
};
