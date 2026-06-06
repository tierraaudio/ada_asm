import { Calendar, Lock, Tag, User } from "lucide-react";
import type { ReactNode } from "react";

import { formatEuros } from "@/lib/format/currency";
import { cn } from "@/lib/utils/cn";

import type { Project, ProjectInterestLink } from "../types";
import { CustomerLink } from "./CustomerLink";
import { InterestLinksField } from "./InterestLinksField";
import { ProjectStatusBadge } from "./ProjectStatusBadge";

interface FieldProps {
  icon?: ReactNode;
  label: string;
  value: ReactNode;
  className?: string;
}

function Field({ icon, label, value, className }: FieldProps) {
  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <dt className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-text-secondary">
        {icon && <span className="text-text-secondary/70">{icon}</span>}
        {label}
      </dt>
      <dd className="text-sm font-medium text-text-primary">{value ?? "—"}</dd>
    </div>
  );
}

function formatDdMmYyyy(iso: string | null | undefined): string {
  if (!iso) return "—";
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

interface ProjectHeaderCardProps {
  project: Project;
  /** Interest-link CRUD handlers — when provided, the right column renders the
   *  full CRUD UI. When omitted, the right column hides itself. */
  interestLinks?: ProjectInterestLink[];
  onAddInterestLink?: ((payload: { name: string; url: string }) => Promise<void>) | undefined;
  onEditInterestLink?:
    | ((id: string, payload: { name: string; url: string }) => Promise<void>)
    | undefined;
  onRemoveInterestLink?: ((id: string) => Promise<void>) | undefined;
}

/**
 * Header card for the project detail page — Figma-faithful 2-column layout.
 *
 * Left column: identity + Estado + Contacto + Color + dates + aggregates +
 * Tags. Right column (Figma right block): Enlaces de interés with full CRUD
 * inline (the same `<InterestLinksField>` used by the edit form).
 */
export function ProjectHeaderCard({
  project,
  interestLinks,
  onAddInterestLink,
  onEditInterestLink,
  onRemoveInterestLink,
}: ProjectHeaderCardProps) {
  const links = interestLinks ?? project.interest_links;
  return (
    <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-start gap-3">
        <span
          aria-hidden
          className="mt-1 inline-flex size-12 shrink-0 items-center justify-center rounded-md text-2xl"
          style={{
            backgroundColor: project.color ? `${project.color}1a` : undefined,
            color: project.color ?? undefined,
          }}
        >
          {project.icon ?? "📁"}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-wide text-text-secondary">
            <span className="font-mono">{project.code}</span>
            {project.version && (
              <span className="ml-2 rounded-md bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">
                {project.version}
              </span>
            )}
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-text-primary">{project.name}</h1>
          {project.description && (
            <p className="mt-1 text-sm text-text-secondary">{project.description}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_440px]">
        {/* ----- Left column: meta + agregados + tags ----- */}
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
            <Field
              icon={<Lock className="size-3.5" />}
              label="Estado"
              value={<ProjectStatusBadge value={project.status} />}
            />
            <Field
              icon={<User className="size-3.5" />}
              label="Contacto asociado"
              value={project.customer ? <CustomerLink customer={project.customer} /> : "—"}
            />
            <Field
              label="Color del proyecto"
              value={
                project.color ? (
                  <span className="inline-flex items-center gap-2">
                    <span
                      aria-hidden
                      className="size-4 rounded-md border border-border"
                      style={{ backgroundColor: project.color }}
                    />
                    <span className="font-mono text-xs">{project.color}</span>
                  </span>
                ) : (
                  "—"
                )
              }
            />

            <Field
              icon={<Calendar className="size-3.5" />}
              label="Fecha de inicio"
              value={formatDdMmYyyy(project.fecha_inicio)}
            />
            <Field
              icon={<Calendar className="size-3.5" />}
              label="Fecha de vencimiento"
              value={formatDdMmYyyy(project.fecha_entrega_estimada)}
            />
            <Field
              icon={<Calendar className="size-3.5" />}
              label="Entrega real"
              value={formatDdMmYyyy(project.fecha_entrega_real)}
            />

            <Field
              label="Precio total"
              value={
                project.precio_total != null ? (
                  <span className="text-brand">{formatEuros(project.precio_total)}</span>
                ) : (
                  "—"
                )
              }
            />
            <Field
              label="Ensamblables"
              value={`${project.buildable_stock} uds`}
            />
            <Field
              label="Última modificación"
              value={formatDdMmYyyy(project.updated_at)}
            />
          </dl>

          {project.tags.length > 0 && (
            <div className="flex flex-col gap-1 border-t border-border pt-3">
              <div className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-text-secondary">
                <Tag className="size-3.5 text-text-secondary/70" aria-hidden />
                Tags
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {project.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-md border border-border bg-muted/50 px-2 py-0.5 text-xs text-text-primary"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ----- Right column: Enlaces de interés (Figma) ----- */}
        <div>
          <InterestLinksField
            links={links}
            disabled={onAddInterestLink === undefined}
            onAdd={onAddInterestLink}
            onEdit={onEditInterestLink}
            onRemove={onRemoveInterestLink}
          />
        </div>
      </div>
    </section>
  );
}
