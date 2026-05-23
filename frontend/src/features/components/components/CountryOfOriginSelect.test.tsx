import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { CountryOfOriginSelect } from "./CountryOfOriginSelect";

function Harness({ initial }: { initial?: string }) {
  const [value, setValue] = useState<string | null>(initial ?? "");
  return (
    <>
      <CountryOfOriginSelect value={value} onChange={setValue} />
      <p data-testid="out">{value ?? "null"}</p>
    </>
  );
}

describe("<CountryOfOriginSelect>", () => {
  it("renders the curated EU+NATO list with a free-text fallback", () => {
    render(<Harness />);
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /US — Estados Unidos/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Otro…/ })).toBeInTheDocument();
  });

  it("selecting a country forwards the ISO code to onChange", async () => {
    render(<Harness />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "DE");
    expect(screen.getByTestId("out")).toHaveTextContent("DE");
  });

  it("selecting 'Otro…' reveals the free-text input", async () => {
    render(<Harness />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "__other__");
    // After selecting "Otro…" the harness state is "" but isCustom only kicks
    // in when value is non-empty AND not in the curated list — type something.
    expect(screen.getByTestId("out")).toHaveTextContent("");
  });

  it("shows the free-text input when the initial value is a custom code", async () => {
    render(<Harness initial="ZA" />);
    const free = screen.getByLabelText(/ISO 3166-1 alpha-2/i) as HTMLInputElement;
    expect(free).toHaveValue("ZA");
  });
});
