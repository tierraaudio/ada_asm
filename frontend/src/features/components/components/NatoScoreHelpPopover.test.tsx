import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { NATO_SCORE_DESCRIPTIONS, NATO_SCORE_LABELS } from "../rubrics";
import { NatoScoreHelpPopover } from "./NatoScoreHelpPopover";

describe("<NatoScoreHelpPopover>", () => {
  it("opens on trigger click and exposes every score from rubrics.ts", async () => {
    render(<NatoScoreHelpPopover />);
    await userEvent.click(
      screen.getByRole("button", { name: /Scoring OTAN/i }),
    );
    const headings = await screen.findAllByText("Scoring OTAN");
    expect(headings.length).toBeGreaterThan(0);
    for (const value of Object.keys(NATO_SCORE_LABELS)) {
      const key = value as keyof typeof NATO_SCORE_LABELS;
      expect(screen.getByText(NATO_SCORE_LABELS[key])).toBeInTheDocument();
      expect(screen.getByText(NATO_SCORE_DESCRIPTIONS[key])).toBeInTheDocument();
    }
  });

  it("closes on Escape", async () => {
    render(<NatoScoreHelpPopover />);
    await userEvent.click(
      screen.getByRole("button", { name: /Scoring OTAN/i }),
    );
    await screen.findByText(NATO_SCORE_LABELS.neutral);
    await userEvent.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByText(NATO_SCORE_LABELS.neutral)).not.toBeInTheDocument();
    });
  });
});
