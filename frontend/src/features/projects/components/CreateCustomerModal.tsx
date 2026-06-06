import { isAxiosError } from "axios";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { useCreateCustomer } from "../hooks/use-customers";
import type { Customer } from "../types";

interface CreateCustomerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the newly created customer after a successful POST. */
  onCreated: (customer: Customer) => void;
}

/**
 * Inline modal for creating a Holded-linked customer from the project edit form.
 * Out of scope: full customer admin UI (no list/edit/delete here) — those are
 * postponed to the Holded sync US.
 */
export function CreateCustomerModal({ open, onOpenChange, onCreated }: CreateCustomerModalProps) {
  const [holdedId, setHoldedId] = useState("");
  const [name, setName] = useState("");
  const [holdedUrl, setHoldedUrl] = useState("");
  const [notas, setNotas] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateCustomer();

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!holdedId.trim() || !name.trim()) {
      setError("Holded ID y Nombre son obligatorios.");
      return;
    }
    try {
      const created = await create.mutateAsync({
        holded_id: holdedId.trim(),
        name: name.trim(),
        holded_url: holdedUrl.trim() ? holdedUrl.trim() : null,
        notas: notas.trim() ? notas.trim() : null,
      });
      onCreated(created);
      setHoldedId("");
      setName("");
      setHoldedUrl("");
      setNotas("");
      onOpenChange(false);
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409) {
        setError("Ya existe un cliente con ese Holded ID.");
      } else {
        setError("No se pudo crear el cliente. Inténtalo de nuevo.");
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <form onSubmit={onSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Nuevo cliente</DialogTitle>
            <DialogDescription>
              Se crea un cliente vinculado a un contacto de Holded. El Holded ID es el
              identificador del cliente en Holded.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 flex flex-col gap-3">
            <Field label="Holded ID *">
              <input
                type="text"
                value={holdedId}
                onChange={(e) => setHoldedId(e.target.value)}
                placeholder="HLD-CUST-XXX"
                className={inputCls}
              />
            </Field>
            <Field label="Nombre *">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ACME Aerospace"
                className={inputCls}
              />
            </Field>
            <Field label="URL Holded (override)">
              <input
                type="text"
                value={holdedUrl}
                onChange={(e) => setHoldedUrl(e.target.value)}
                placeholder="https://app.holded.com/contact/..."
                className={inputCls}
              />
            </Field>
            <Field label="Notas">
              <textarea
                rows={2}
                value={notas}
                onChange={(e) => setNotas(e.target.value)}
                className={inputCls}
              />
            </Field>
            {error && (
              <p role="alert" className="text-xs text-red-600">
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={create.isPending}>
              Crear cliente
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const inputCls =
  "h-10 w-full rounded-md border border-border bg-white px-3 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-text-primary">{label}</label>
      {children}
    </div>
  );
}
