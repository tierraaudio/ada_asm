import { Edit3, Link2, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDeleteDialog } from "@/features/components/components/ConfirmDeleteDialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

import type { ProjectInterestLink } from "../types";

/**
 * Manages the "Enlaces de interés" sub-form inside the project editor.
 *
 * In create mode, the project doesn't exist yet — there's no place to POST
 * links. The component renders disabled with a helpful note so the UX
 * matches the form's general "save first" pattern.
 *
 * In edit mode, each link CRUDs against the project's `/interest-links`
 * sub-resource directly via the parent-supplied callbacks. The parent owns
 * the mutation hooks so this primitive stays presentational.
 */
export interface InterestLinksFieldProps {
  /** Empty array in create mode. Hydrated server-side in edit mode. */
  links: ProjectInterestLink[];
  /** Disabled in create mode (project hasn't been persisted). */
  disabled?: boolean;
  /** POST a new link. Returns the created entity so the parent can refetch. */
  onAdd?: ((payload: { name: string; url: string }) => Promise<void>) | undefined;
  /** PATCH an existing link. */
  onEdit?: ((id: string, payload: { name: string; url: string }) => Promise<void>) | undefined;
  /** DELETE a link. */
  onRemove?: ((id: string) => Promise<void>) | undefined;
}

export function InterestLinksField({
  links,
  disabled = false,
  onAdd,
  onEdit,
  onRemove,
}: InterestLinksFieldProps) {
  const [addingOpen, setAddingOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-2">
      <p className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
        <Link2 className="size-3.5 text-text-secondary" />
        Enlaces de interés
      </p>

      {disabled && (
        <p className="text-xs text-text-secondary">
          Guarda el proyecto para empezar a añadir enlaces.
        </p>
      )}

      <div className="rounded-md border border-border bg-muted/20 p-2">
        {links.length === 0 && !addingOpen && !disabled && (
          <p className="px-2 py-1 text-xs text-text-secondary">
            Sin enlaces todavía.
          </p>
        )}

        <ul className="flex flex-col gap-1">
          {links.map((link) =>
            editingId === link.id ? (
              <li key={link.id}>
                <InterestLinkForm
                  initialName={link.name}
                  initialUrl={link.url}
                  submitLabel="Guardar"
                  onSubmit={async (payload) => {
                    await onEdit?.(link.id, payload);
                    setEditingId(null);
                  }}
                  onCancel={() => setEditingId(null)}
                />
              </li>
            ) : (
              <li
                key={link.id}
                className="flex items-center gap-2 rounded-md border border-border bg-white px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <p
                        className="truncate text-sm font-medium text-text-primary"
                        title={link.name}
                      >
                        {link.name}
                      </p>
                    </TooltipTrigger>
                    <TooltipContent side="top" align="start" className="max-w-md break-words">
                      {link.name}
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <a
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block truncate text-xs text-text-secondary hover:underline"
                        title={link.url}
                      >
                        {link.url}
                      </a>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" align="start" className="max-w-md break-all">
                      {link.url}
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="ml-2 flex shrink-0 items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    aria-label="Editar enlace"
                    disabled={disabled}
                    onClick={() => setEditingId(link.id)}
                  >
                    <Edit3 className="size-4 text-text-secondary" />
                  </Button>
                  <ConfirmDeleteDialog
                    trigger={
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        aria-label="Eliminar enlace"
                        disabled={disabled}
                      >
                        <Trash2 className="size-4 text-red-600" />
                      </Button>
                    }
                    title={`¿Eliminar el enlace «${link.name}»?`}
                    description="El enlace se quita del proyecto. Esta acción no se puede deshacer."
                    confirmLabel="Eliminar"
                    onConfirm={async () => {
                      await onRemove?.(link.id);
                    }}
                  />
                </div>
              </li>
            ),
          )}

          {addingOpen && (
            <li>
              <InterestLinkForm
                submitLabel="Añadir"
                onSubmit={async (payload) => {
                  await onAdd?.(payload);
                  setAddingOpen(false);
                }}
                onCancel={() => setAddingOpen(false)}
              />
            </li>
          )}
        </ul>

        {!addingOpen && !disabled && (
          <button
            type="button"
            onClick={() => setAddingOpen(true)}
            className={cn(
              "mt-2 inline-flex w-full items-center justify-center gap-1.5",
              "rounded-md border border-dashed border-border bg-white px-3 py-2",
              "text-sm text-text-secondary hover:border-brand hover:text-brand",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand",
            )}
          >
            <Plus className="size-4" />
            Añadir enlace
          </button>
        )}
      </div>
    </div>
  );
}

interface InterestLinkFormProps {
  initialName?: string;
  initialUrl?: string;
  submitLabel: string;
  onSubmit: (payload: { name: string; url: string }) => Promise<void>;
  onCancel: () => void;
}

function InterestLinkForm({
  initialName = "",
  initialUrl = "",
  submitLabel,
  onSubmit,
  onCancel,
}: InterestLinkFormProps) {
  const [name, setName] = useState(initialName);
  const [url, setUrl] = useState(initialUrl);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !url.trim()) {
      setError("Nombre y URL son obligatorios.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ name: name.trim(), url: url.trim() });
    } catch (err) {
      console.error(err);
      setError("No se pudo guardar. Inténtalo de nuevo.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-md border border-border bg-white p-3">
      <div className="flex flex-col gap-2">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nombre del enlace"
          className={inputCls}
        />
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          className={inputCls}
        />
        {error && (
          <p role="alert" className="text-xs text-red-600">
            {error}
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant="default"
            size="sm"
            disabled={submitting}
            onClick={handleSubmit}
          >
            {submitLabel}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onCancel}
            disabled={submitting}
          >
            <X className="size-4" />
            Cancelar
          </Button>
        </div>
      </div>
    </div>
  );
}

const inputCls =
  "h-10 w-full rounded-md border border-border bg-white px-3 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";
