import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { createElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";

import { useComponents } from "./use-components";

const API = "http://localhost:8000";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return createElement(QueryClientProvider, { client }, children);
}

describe("useComponents", () => {
  it("forwards filters and pagination to the API as query params", async () => {
    let capturedUrl: URL | null = null;
    server.use(
      http.get(`${API}/api/v1/components`, ({ request }) => {
        capturedUrl = new URL(request.url);
        return HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 25,
        });
      }),
    );

    const { result } = renderHook(
      () =>
        useComponents({
          filters: {
            q: "esp",
            family: "Microcontroladores",
            supplier: "Mouser",
            tier: "A",
            nato_score: "high_risk",
          },
          page: 2,
          pageSize: 50,
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(capturedUrl).not.toBeNull();
    const params = (capturedUrl as unknown as URL).searchParams;
    expect(params.get("q")).toBe("esp");
    expect(params.get("family")).toBe("Microcontroladores");
    expect(params.get("supplier")).toBe("Mouser");
    expect(params.get("tier")).toBe("A");
    expect(params.get("nato_score")).toBe("high_risk");
    expect(params.get("page")).toBe("2");
    expect(params.get("page_size")).toBe("50");
  });

  it("omits empty / unset filters from the request", async () => {
    let capturedUrl: URL | null = null;
    server.use(
      http.get(`${API}/api/v1/components`, ({ request }) => {
        capturedUrl = new URL(request.url);
        return HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 25,
        });
      }),
    );

    const { result } = renderHook(
      () => useComponents({ filters: { q: "   " }, page: 1, pageSize: 25 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const params = (capturedUrl as unknown as URL).searchParams;
    expect(params.get("q")).toBeNull();
    expect(params.get("family")).toBeNull();
    expect(params.get("tier")).toBeNull();
  });
});
