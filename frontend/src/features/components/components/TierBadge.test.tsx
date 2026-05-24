import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TIER_VALUES } from "../types";
import { TierBadge } from "./TierBadge";

describe("<TierBadge>", () => {
  it.each(TIER_VALUES)("renders 'Tier %s' as the literal label", (value) => {
    render(<TierBadge value={value} />);
    expect(screen.getByText(`Tier ${value}`)).toBeInTheDocument();
  });

  it("sets an accessible aria-label", () => {
    render(<TierBadge value={1} />);
    expect(screen.getByLabelText(/Tier 1/)).toBeInTheDocument();
  });
});
