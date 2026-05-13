import { describe, expect, it } from "vitest";

import { useAuthStore } from "./auth-store";
import { sampleUser } from "@/tests/utils";

describe("auth-store", () => {
  it("starts anonymous with no token / user", () => {
    const state = useAuthStore.getState();
    expect(state.status).toBe("anonymous");
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
  });

  it("setSession populates token, user and flips status", () => {
    useAuthStore.getState().setSession("token-xyz", sampleUser);
    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("token-xyz");
    expect(state.user).toEqual(sampleUser);
    expect(state.status).toBe("authenticated");
  });

  it("clearSession resets the store", () => {
    useAuthStore.getState().setSession("token-xyz", sampleUser);
    useAuthStore.getState().clearSession();
    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.status).toBe("anonymous");
  });
});
