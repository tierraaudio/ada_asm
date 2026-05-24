import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/tests/utils";

import { NATO_SCORE_RUBRIC } from "../rubrics";
import { NatoScoreHelpPopover } from "./NatoScoreHelpPopover";

describe("<NatoScoreHelpPopover>", () => {
  it("opens on click and exposes the rubric copy verbatim", async () => {
    renderWithProviders(<NatoScoreHelpPopover />);
    await userEvent.click(screen.getByRole("button", { name: /Scoring OTAN/i }));
    expect(await screen.findByText(/Niveles de clasificación:/)).toBeInTheDocument();
    expect(screen.getByText(NATO_SCORE_RUBRIC["A+"])).toBeInTheDocument();
    expect(screen.getByText(NATO_SCORE_RUBRIC.F)).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    renderWithProviders(<NatoScoreHelpPopover />);
    await userEvent.click(screen.getByRole("button", { name: /Scoring OTAN/i }));
    await screen.findByText(/Niveles de clasificación:/);
    await userEvent.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByText(/Niveles de clasificación:/)).not.toBeInTheDocument();
    });
  });
});
