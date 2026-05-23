import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NATO_SCORE_LABELS } from "../rubrics";
import { NATO_SCORE_VALUES } from "../types";
import { NatoScoreBadge } from "./NatoScoreBadge";

describe("<NatoScoreBadge>", () => {
  it.each(NATO_SCORE_VALUES)(
    "renders the Spanish label for value %s",
    (value) => {
      render(<NatoScoreBadge value={value} />);
      expect(screen.getByText(NATO_SCORE_LABELS[value])).toBeInTheDocument();
    },
  );
});
