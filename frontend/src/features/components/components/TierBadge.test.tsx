import { act, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/tests/utils";

import { TIER_RUBRIC } from "../rubrics";
import { TIER_VALUES } from "../types";
import { TierBadge } from "./TierBadge";

describe("<TierBadge>", () => {
  it.each(TIER_VALUES)("renders 'Tier %s' as the literal label", (value) => {
    renderWithProviders(<TierBadge value={value} />);
    expect(screen.getByText(`Tier ${value}`)).toBeInTheDocument();
  });

  it("sets an accessible aria-label", () => {
    renderWithProviders(<TierBadge value={1} />);
    expect(screen.getByLabelText(/Tier 1/)).toBeInTheDocument();
  });

  it("shows the category + risk via tooltip on focus", async () => {
    renderWithProviders(<TierBadge value={1} />);
    // jsdom doesn't fire pointer events reliably for Radix; focus dispatches
    // cleanly and Radix opens the tooltip the same way for keyboard users.
    await act(async () => {
      screen.getByLabelText(/Tier 1/).focus();
    });
    // Radix renders tooltip content twice (visible + visually-hidden) — match >= 1.
    expect((await screen.findAllByText(TIER_RUBRIC[1].category)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Riesgo: Muy alto/).length).toBeGreaterThan(0);
  });

  it("skips the tooltip when withTooltip is false", () => {
    renderWithProviders(<TierBadge value={2} withTooltip={false} />);
    const badge = screen.getByLabelText(/Tier 2/);
    expect(badge).not.toHaveAttribute("tabIndex", "0");
  });
});
