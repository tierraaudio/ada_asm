import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { REFRESH_TOKEN_KEY, clearRefreshToken, readRefreshToken, writeRefreshToken } from "./token-storage";

describe("token-storage", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it("reads null when nothing has been written", () => {
    expect(readRefreshToken()).toBeNull();
  });

  it("writes and reads the same value", () => {
    writeRefreshToken("abc-123");
    expect(readRefreshToken()).toBe("abc-123");
    expect(window.localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("abc-123");
  });

  it("clears removes the entry", () => {
    writeRefreshToken("abc-123");
    clearRefreshToken();
    expect(readRefreshToken()).toBeNull();
    expect(window.localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
  });
});
