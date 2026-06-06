import { useNavigate } from "react-router-dom";

import { ProjectStatusBadge } from "@/features/projects/components/ProjectStatusBadge";
import { formatEuros } from "@/lib/format/currency";
import { cn } from "@/lib/utils/cn";

import type { ProjectSummary } from "@/features/projects/types";

interface ProjectsHierarchyRowProps {
  project: ProjectSummary;
  className?: string;
}

/**
 * Flat one-line row used by the "Usado en proyectos" sections on Component
 * and Module detail. Same interaction language as the canonical hierarchy
 * tables: the entire row is clickable and navigates to the project detail.
 * No explicit affordance button — homogeneous with the modules/components/
 * projects tables.
 */
export function ProjectsHierarchyRow({ project, className }: ProjectsHierarchyRowProps) {
  const navigate = useNavigate();
  const go = () => navigate(`/projects/${project.id}`);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={go}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          go();
        }
      }}
      className={cn(
        "flex cursor-pointer items-center justify-between gap-4 border-t border-border px-3 py-2",
        "hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/40",
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="font-mono text-xs text-text-secondary">{project.code}</span>
        <span className="truncate text-sm font-medium text-text-primary">{project.name}</span>
        <ProjectStatusBadge value={project.status} />
        {project.customer && (
          <span className="truncate text-xs text-text-secondary">
            {project.customer.name}
          </span>
        )}
      </div>
      <span className="shrink-0 text-xs font-semibold text-brand">
        {project.precio_total != null ? formatEuros(project.precio_total) : "—"}
      </span>
    </div>
  );
}
