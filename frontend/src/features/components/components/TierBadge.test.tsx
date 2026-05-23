import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TIER_VALUES } from "../types";
import { TierBadge } from "./TierBadge";

describe("<TierBadge>", () => {
  it.each(TIER_VALUES)("renders the literal label for value %s", (value) => {
    render(<TierBadge value={value} />);
    expect(screen.getByText(value)).toBeInTheDocument();
  });

  it("sets an accessible aria-label", () => {
    render(<TierBadge value="A+" />);
    expect(screen.getByLabelText(/Tier A\+/)).toBeInTheDocument();
  });
});
