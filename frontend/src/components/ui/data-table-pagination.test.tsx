import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DataTablePagination } from "./data-table-pagination";

describe("<DataTablePagination>", () => {
  it("renders the 'page X of Y · N resultados' summary by default", () => {
    render(<DataTablePagination page={2} pageCount={5} total={120} onPageChange={vi.fn()} />);
    expect(screen.getByText(/Página 2 de 5 · 120 resultados/)).toBeInTheDocument();
  });

  it("invokes onPageChange with the right targets for each arrow", async () => {
    const onPageChange = vi.fn();
    render(<DataTablePagination page={3} pageCount={10} total={250} onPageChange={onPageChange} />);

    await userEvent.click(screen.getByRole("button", { name: /Ir a la primera página/i }));
    await userEvent.click(screen.getByRole("button", { name: /Página anterior/i }));
    await userEvent.click(screen.getByRole("button", { name: /Página siguiente/i }));
    await userEvent.click(screen.getByRole("button", { name: /Ir a la última página/i }));

    expect(onPageChange).toHaveBeenNthCalledWith(1, 1);
    expect(onPageChange).toHaveBeenNthCalledWith(2, 2);
    expect(onPageChange).toHaveBeenNthCalledWith(3, 4);
    expect(onPageChange).toHaveBeenNthCalledWith(4, 10);
  });

  it("disables the left pair on the first page", () => {
    render(<DataTablePagination page={1} pageCount={5} total={120} onPageChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /primera página/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Página anterior/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Página siguiente/i })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /última página/i })).not.toBeDisabled();
  });

  it("disables the right pair on the last page", () => {
    render(<DataTablePagination page={5} pageCount={5} total={120} onPageChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Página siguiente/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /última página/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Página anterior/i })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /primera página/i })).not.toBeDisabled();
  });

  it("accepts a custom summary", () => {
    render(
      <DataTablePagination
        page={1}
        pageCount={1}
        total={5}
        onPageChange={vi.fn()}
        summary={<span>custom summary</span>}
      />,
    );
    expect(screen.getByText("custom summary")).toBeInTheDocument();
  });
});
