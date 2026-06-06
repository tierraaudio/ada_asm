import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { DetailNavControls } from "./DetailNavControls";
import { useDetailNavStack } from "./DetailNavStack";

interface DetailPageHeaderProps {
  /** Pathname to navigate to when the X is pressed (returns to a list page).
   *  The detail nav stack is reset on close. */
  closeTo: string;
  /** Action(s) rendered on the right side of the bar (typically an "Editar"
   *  button or a Cancel / Save pair on edit forms). */
  rightSlot?: ReactNode;
  /** Imperative override for the close handler (used by edit pages that need
   *  to navigate back to the entity's detail view rather than the list). */
  onClose?: () => void;
}

/**
 * Sticky top bar shared by component & module detail/edit pages.
 *
 * Layout: `X` close + `<` `>` nav-stack controls on the left, an optional
 * action slot on the right. Pinned at the top of the page while content
 * scrolls underneath — opaque background hides the content beneath, with
 * a 1px hairline shadow under the bar.
 *
 * Render this as the first child of the page so `top-0` pins flush against
 * the visible top of `<main>` (whose top padding was removed for that
 * purpose).
 */
export function DetailPageHeader({ closeTo, rightSlot, onClose }: DetailPageHeaderProps) {
  const { reset } = useDetailNavStack();
  const navigate = useNavigate();

  const handleClose = () => {
    if (onClose) {
      onClose();
      return;
    }
    reset();
    navigate(closeTo);
  };

  return (
    <header className="sticky top-0 z-10 -mx-6 flex items-center justify-between bg-page-bg px-6 py-4 shadow-[0_1px_0_0_hsl(var(--border))]">
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Cerrar"
          onClick={handleClose}
          className="inline-flex size-9 items-center justify-center rounded-md text-text-secondary hover:bg-muted hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          <X className="size-5" />
        </button>
        <DetailNavControls />
      </div>
      {rightSlot ? <div className="flex items-center gap-2">{rightSlot}</div> : null}
    </header>
  );
}
