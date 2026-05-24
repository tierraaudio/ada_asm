import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TIER_RUBRIC } from "../rubrics";
import { TierHelpPopover } from "./TierHelpPopover";

describe("<TierHelpPopover>", () => {
  it("opens and shows the four tier categories with risk levels", async () => {
    render(<TierHelpPopover />);
    await userEvent.click(screen.getByRole("button", { name: /TIER/i }));
    expect(await screen.findByText(/Niveles de TIER:/)).toBeInTheDocument();
    expect(screen.getByText(TIER_RUBRIC[1].category)).toBeInTheDocument();
    expect(screen.getByText(TIER_RUBRIC[4].category)).toBeInTheDocument();
    expect(screen.getAllByText(/Riesgo:/).length).toBe(4);
  });
});
