import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { useDetailNavStack } from "./DetailNavStack";

/**
 * `<` `>` navigation pair surfaced on detail and edit pages, paired with
 * the existing `X` close button. Drives the in-memory navigation stack
 * defined by `DetailNavStackProvider`.
 */
export function DetailNavControls() {
  const { canGoBack, canGoForward, goBack, goForward } = useDetailNavStack();
  return (
    <div className="inline-flex items-center gap-1">
      <button
        type="button"
        aria-label="Anterior"
        disabled={!canGoBack}
        onClick={goBack}
        className="inline-flex size-9 items-center justify-center rounded-md text-text-secondary hover:bg-muted hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:text-text-secondary/30 disabled:hover:bg-transparent"
      >
        <ChevronLeft className="size-5" />
      </button>
      <button
        type="button"
        aria-label="Siguiente"
        disabled={!canGoForward}
        onClick={goForward}
        className="inline-flex size-9 items-center justify-center rounded-md text-text-secondary hover:bg-muted hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:text-text-secondary/30 disabled:hover:bg-transparent"
      >
        <ChevronRight className="size-5" />
      </button>
    </div>
  );
}

/**
 * Pushes the current pathname onto the detail nav stack on mount and when
 * the pathname changes. Pages call this once at the top of their render.
 */
export function useDetailNavPush() {
  const { push } = useDetailNavStack();
  const { pathname } = useLocation();
  useEffect(() => {
    push(pathname);
  }, [pathname, push]);
}
