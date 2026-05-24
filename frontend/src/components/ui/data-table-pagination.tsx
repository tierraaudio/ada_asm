import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

export interface DataTablePaginationProps {
  /** 1-based current page. */
  page: number;
  /** Total page count (>= 1). */
  pageCount: number;
  /** Total row count (used for the "N resultados" summary). */
  total: number;
  /** Callback when the user picks a different page (1-based). */
  onPageChange: (page: number) => void;
  /** Custom summary slot. Defaults to "Página X de Y · N resultados". */
  summary?: ReactNode;
  className?: string;
}

/**
 * Pagination controls for every data table in the project: first / prev /
 * next / last, plus a "Página X de Y · N resultados" summary. Self-disables
 * the right pair when on the last page and the left pair when on the first.
 * Designed to be lifted into `DataTable` if/when we extract a single wrapper.
 */
export function DataTablePagination({
  page,
  pageCount,
  total,
  onPageChange,
  summary,
  className,
}: DataTablePaginationProps) {
  const atFirst = page <= 1;
  const atLast = page >= pageCount;
  return (
    <div
      className={cn("flex items-center justify-end gap-2 text-sm text-text-secondary", className)}
      role="navigation"
      aria-label="Paginación"
    >
      <span className="mr-2">
        {summary ?? (
          <>
            Página {page} de {pageCount} · {total} resultados
          </>
        )}
      </span>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-8"
        aria-label="Ir a la primera página"
        disabled={atFirst}
        onClick={() => onPageChange(1)}
      >
        <ChevronsLeft className="size-4" />
      </Button>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-8"
        aria-label="Página anterior"
        disabled={atFirst}
        onClick={() => onPageChange(page - 1)}
      >
        <ChevronLeft className="size-4" />
      </Button>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-8"
        aria-label="Página siguiente"
        disabled={atLast}
        onClick={() => onPageChange(page + 1)}
      >
        <ChevronRight className="size-4" />
      </Button>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-8"
        aria-label="Ir a la última página"
        disabled={atLast}
        onClick={() => onPageChange(pageCount)}
      >
        <ChevronsRight className="size-4" />
      </Button>
    </div>
  );
}
