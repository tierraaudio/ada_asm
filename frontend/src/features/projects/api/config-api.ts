import { api } from "@/lib/api/client";

import type { ConfigResponse } from "../types";

export const configApi = {
  get: async (): Promise<ConfigResponse> => {
    const response = await api.get<ConfigResponse>("/api/v1/config");
    return response.data;
  },
};
