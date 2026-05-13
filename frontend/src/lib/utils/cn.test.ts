import { describe, expect, it } from "vitest";

import { cn } from "./cn";

describe("cn", () => {
  it("joins truthy class values", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("filters falsy values", () => {
    expect(cn("a", false && "b", null, undefined, "")).toBe("a");
  });

  it("lets later Tailwind utilities win on conflict", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
});
