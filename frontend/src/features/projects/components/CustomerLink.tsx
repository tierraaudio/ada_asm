import { ExternalLink } from "lucide-react";

import { cn } from "@/lib/utils/cn";

import { useConfig } from "../hooks/use-config";
import type { Customer } from "../types";

export interface CustomerLinkProps {
  customer: Customer;
  /** Compact mode (used inside tables) — single line, smaller external icon. */
  compact?: boolean;
  className?: string;
}

/**
 * Renders the customer NAME as a link to Holded.
 *
 * Hierarchy for the href: explicit `customer.holded_url` override wins;
 * otherwise it's built from `${config.holded_base_url}/contact/{holded_id}`.
 * The `holded_id` is intentionally NOT rendered (the link IS the indirection
 * to Holded — the id only matters at sync time, not in the UI).
 *
 * Disabled plain text while the config is loading, so the user never sees
 * a broken `href`.
 */
export function CustomerLink({ customer, compact = false, className }: CustomerLinkProps) {
  const configQuery = useConfig();
  const explicit = customer.holded_url?.trim();
  const builtHref =
    explicit ||
    (configQuery.data
      ? `${configQuery.data.holded_base_url.replace(/\/+$/, "")}/contact/${customer.holded_id}`
      : null);

  if (!builtHref) {
    return (
      <span className={cn("text-sm text-text-secondary", className)}>{customer.name}</span>
    );
  }

  return (
    <a
      href={builtHref}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "inline-flex items-center gap-1.5 text-sm text-text-primary hover:underline focus-visible:underline",
        className,
      )}
    >
      <span className="truncate">{customer.name}</span>
      <ExternalLink
        className={cn("shrink-0 text-text-secondary", compact ? "size-3" : "size-3.5")}
        aria-hidden
      />
    </a>
  );
}
