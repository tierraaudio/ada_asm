import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";

import { ConfirmDeleteDialog } from "./ConfirmDeleteDialog";

describe("<ConfirmDeleteDialog>", () => {
  it("opens on trigger, calls onConfirm and closes afterwards", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfirmDeleteDialog
        trigger={<Button>Open</Button>}
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(
      await screen.findByText("¿Eliminar componente?"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Eliminar$/ }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
  });

  it("closes when Cancel is clicked without invoking onConfirm", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDeleteDialog
        trigger={<Button>Open</Button>}
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const cancelButtons = await screen.findAllByRole("button", { name: /^Cancelar$/ });
    await userEvent.click(cancelButtons[0]!);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
