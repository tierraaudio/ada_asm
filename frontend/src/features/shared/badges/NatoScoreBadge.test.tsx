import { act, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/tests/utils";

import { NATO_SCORE_LABELS, NATO_SCORE_RUBRIC } from "@/features/shared/rubrics";
import { NATO_SCORE_VALUES } from "@/features/shared/enums";
import { NatoScoreBadge } from "./NatoScoreBadge";

describe("<NatoScoreBadge>", () => {
  it.each(NATO_SCORE_VALUES)("renders the letter '%s' as label", (value) => {
    renderWithProviders(<NatoScoreBadge value={value} />);
    expect(screen.getByText(NATO_SCORE_LABELS[value])).toBeInTheDocument();
  });

  it("shows the rubric text via tooltip on focus", async () => {
    renderWithProviders(<NatoScoreBadge value="A+" />);
    await act(async () => {
      screen.getByLabelText(/Scoring OTAN A\+/).focus();
    });
    // Radix renders tooltip content twice (visible + visually-hidden) — match >= 1.
    expect((await screen.findAllByText(NATO_SCORE_RUBRIC["A+"])).length).toBeGreaterThan(0);
  });

  it("skips the tooltip when withTooltip is false", () => {
    renderWithProviders(<NatoScoreBadge value="A" withTooltip={false} />);
    expect(screen.getByLabelText(/Scoring OTAN A/)).not.toHaveAttribute("tabIndex", "0");
  });
});
