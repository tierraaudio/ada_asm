import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { Calendar, MapPin, Package, Plus, Save } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TIPO_ALMACENAMIENTO_VALUES } from "@/features/shared/enums";
import { useDetailNavPush } from "@/features/shared/nav/DetailNavControls";
import { useDetailNavStack } from "@/features/shared/nav/DetailNavStack";
import { DetailPageHeader } from "@/features/shared/nav/DetailPageHeader";
import { cn } from "@/lib/utils/cn";

import { AddChildModal } from "../components/AddChildModal";
import { ModulesHierarchyTable } from "../components/ModulesHierarchyTable";
import { useModuleDetail } from "../hooks/use-module-detail";
import {
  useAddChild,
  useCreateModule,
  useRemoveChild,
  useUpdateModule,
} from "../hooks/use-module-mutations";
import { MODULE_FAMILY_VALUES } from "../types";

function formatDdMmYyyy(iso: string | null | undefined): string {
  if (!iso) return "—";
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

interface ModuleEditPageProps {
  mode: "create" | "edit";
}

const formSchema = z.object({
  sku: z.string().trim().min(1, "SKU obligatorio").max(100),
  name: z.string().trim().min(1, "Nombre obligatorio").max(200),
  description: z.string().optional(),
  version: z.string().trim().max(40).optional(),
  family: z
    .string()
    .min(1, "Familia obligatoria")
    .refine((v) => (MODULE_FAMILY_VALUES as readonly string[]).includes(v), "Familia inválida"),
  fabricante: z.string().trim().max(120).optional(),
  location: z.string().trim().max(100).optional(),
  tipo_almacenamiento: z
    .string()
    .optional()
    .refine(
      (v) => !v || (TIPO_ALMACENAMIENTO_VALUES as readonly string[]).includes(v),
      "Valor inválido",
    ),
  stock: z.coerce.number().int().min(0, "Stock no puede ser negativo"),
  notas: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

const EMPTY_DEFAULTS: FormValues = {
  sku: "",
  name: "",
  description: "",
  version: "v1.0",
  family: "Board",
  fabricante: "",
  location: "",
  tipo_almacenamiento: "",
  stock: 0,
  notas: "",
};

export function ModuleEditPage({ mode }: ModuleEditPageProps) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const isEdit = mode === "edit";
  const [pickerOpen, setPickerOpen] = useState(false);
  const { reset: resetNavStack } = useDetailNavStack();
  useDetailNavPush();

  const detailQuery = useModuleDetail(isEdit ? id : undefined);
  const create = useCreateModule();
  const update = useUpdateModule();
  const addChild = useAddChild();
  const removeChild = useRemoveChild();

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: EMPTY_DEFAULTS,
  });

  useEffect(() => {
    if (!isEdit || !detailQuery.data) return;
    const m = detailQuery.data;
    reset({
      sku: m.sku,
      name: m.name,
      description: m.description ?? "",
      version: m.version,
      family: m.family,
      fabricante: m.fabricante ?? "",
      location: m.location ?? "",
      tipo_almacenamiento: m.tipo_almacenamiento ?? "",
      stock: m.stock,
      notas: m.notas ?? "",
    });
  }, [isEdit, detailQuery.data, reset]);

  const onCancel = () => {
    if (isEdit && id) navigate(`/modules/${id}`);
    else navigate("/modules");
  };

  const onClose = () => {
    resetNavStack();
    navigate("/modules");
  };

  const submitWith = (afterCreate: "detail" | "edit_open_picker") =>
    handleSubmit(async (values) => {
      const payload: Record<string, unknown> = {
        sku: values.sku.trim(),
        name: values.name.trim(),
        description: values.description?.trim() ? values.description.trim() : null,
        family: values.family,
        fabricante: values.fabricante?.trim() ? values.fabricante.trim() : null,
        location: values.location?.trim() ? values.location.trim() : null,
        tipo_almacenamiento: values.tipo_almacenamiento?.trim()
          ? values.tipo_almacenamiento.trim()
          : null,
        stock: values.stock,
        notas: values.notas?.trim() ? values.notas.trim() : null,
      };
      if (values.version?.trim()) payload["version"] = values.version.trim();
      try {
        if (isEdit && id) {
          await update.mutateAsync({ id, payload: payload as Record<string, never> });
          if (afterCreate === "edit_open_picker") setPickerOpen(true);
          else navigate(`/modules/${id}`);
        } else {
          const created = await create.mutateAsync(
            payload as unknown as { sku: string; name: string },
          );
          if (afterCreate === "edit_open_picker") {
            navigate(`/modules/${created.id}/edit?add_child=1`);
          } else {
            navigate(`/modules/${created.id}`);
          }
        }
      } catch (err) {
        // Surfaced in the banner below via mutation.error state.
        console.error(err);
      }
    });

  const onSubmit = submitWith("detail");
  const onSaveAndAddChild = submitWith("edit_open_picker");

  // Auto-open the Add-child picker after a "save & add child" hand-off from
  // the create form.
  useEffect(() => {
    if (!isEdit) return;
    if (searchParams.get("add_child") !== "1") return;
    if (!detailQuery.data) return;
    setPickerOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete("add_child");
    setSearchParams(next, { replace: true });
  }, [isEdit, detailQuery.data, searchParams, setSearchParams]);

  const submitError =
    create.error && isAxiosError(create.error) && create.error.response?.status === 409
      ? "Ya existe un módulo con ese SKU."
      : update.error
        ? "No se pudo guardar. Inténtalo de nuevo."
        : null;

  if (isEdit && id && detailQuery.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando módulo…</p>
      </DashboardLayout>
    );
  }
  if (isEdit && (detailQuery.isError || (id && !detailQuery.data))) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el módulo.</p>
      </DashboardLayout>
    );
  }

  const module = detailQuery.data;

  return (
    <DashboardLayout>
      <form
        noValidate
        onSubmit={onSubmit}
        className="mx-auto flex w-full max-w-[1920px] flex-col gap-6"
        aria-label={isEdit ? "Editar módulo" : "Nuevo módulo"}
      >
        <DetailPageHeader
          closeTo="/modules"
          onClose={onClose}
          rightSlot={
            <>
              <Button type="button" variant="outline" size="sm" onClick={onCancel}>
                Cancelar
              </Button>
              <Button type="submit" size="sm" disabled={isSubmitting || (isEdit && !isDirty)}>
                <Save className="size-4" />
                {isEdit ? "Guardar cambios" : "Crear módulo"}
              </Button>
            </>
          }
        />

        {submitError && (
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
          >
            {submitError}
          </div>
        )}

        <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
          {/* Row 1: SKU + Versión */}
          <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
            <FormField label="SKU" error={errors.sku?.message}>
              <input
                {...register("sku")}
                type="text"
                className={inputCls}
                placeholder="MOD-SENS-001"
              />
            </FormField>
            <FormField label="Versión" error={errors.version?.message}>
              <input {...register("version")} type="text" className={inputCls} placeholder="v1.0" />
            </FormField>
          </div>

          {/* Row 2: Nombre */}
          <div className="mt-4">
            <FormField label="Nombre" error={errors.name?.message}>
              <input
                {...register("name")}
                type="text"
                className={inputCls}
                placeholder="Módulo Sensor Ambiental"
              />
            </FormField>
          </div>

          {/* Row 3: Descripción */}
          <div className="mt-4">
            <FormField label="Descripción" error={errors.description?.message}>
              <textarea
                {...register("description")}
                rows={3}
                className={cn(inputCls, "min-h-[80px] resize-y")}
              />
            </FormField>
          </div>

          {/* Row 4: Audit strip — only in edit mode */}
          {isEdit && module && (
            <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-border pt-4 md:grid-cols-4">
              <ReadonlyField
                icon={<Calendar className="size-3.5" />}
                label="Fecha de creación"
                value={formatDdMmYyyy(module.fecha_creacion)}
              />
              <ReadonlyField
                icon={<Calendar className="size-3.5" />}
                label="Última modificación"
                value={formatDdMmYyyy(module.updated_at)}
              />
            </div>
          )}

          {/* Row 5: Ubicación + Tipo almacenamiento + Familia */}
          <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2 lg:grid-cols-3">
            <FormField
              label="Ubicación"
              icon={<MapPin className="size-3.5" />}
              error={errors.location?.message}
            >
              <input
                {...register("location")}
                type="text"
                className={inputCls}
                placeholder="G-M-01"
              />
            </FormField>
            <FormField
              label="Tipo almacenamiento"
              icon={<Package className="size-3.5" />}
              error={errors.tipo_almacenamiento?.message}
            >
              <Controller
                control={control}
                name="tipo_almacenamiento"
                render={({ field }) => (
                  <Select
                    value={field.value ? field.value : "__none__"}
                    onValueChange={(v) => field.onChange(v === "__none__" ? "" : v)}
                  >
                    <SelectTrigger className={inputCls}>
                      <SelectValue placeholder="Selecciona…" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">—</SelectItem>
                      {TIPO_ALMACENAMIENTO_VALUES.map((v) => (
                        <SelectItem key={v} value={v}>
                          {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FormField>
            <FormField
              label="Familia"
              icon={<Package className="size-3.5" />}
              error={errors.family?.message}
            >
              <Controller
                control={control}
                name="family"
                render={({ field }) => (
                  <Select
                    {...(field.value ? { value: field.value } : {})}
                    onValueChange={(v) => field.onChange(v)}
                  >
                    <SelectTrigger className={inputCls}>
                      <SelectValue placeholder="Selecciona familia…" />
                    </SelectTrigger>
                    <SelectContent>
                      {MODULE_FAMILY_VALUES.map((v) => (
                        <SelectItem key={v} value={v}>
                          {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FormField>
          </div>

          {/* Row 6: Fabricante + Stock (ensamblados) */}
          <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
            <FormField label="Fabricante" error={errors.fabricante?.message}>
              <input
                {...register("fabricante")}
                type="text"
                className={inputCls}
                placeholder="Custom Assembly"
              />
            </FormField>
            <FormField label="Stock (ensamblados)" error={errors.stock?.message}>
              <input
                {...register("stock")}
                type="number"
                min={0}
                className={inputCls}
                placeholder="0"
              />
            </FormField>
          </div>
        </section>

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Contiene
            </h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isSubmitting}
              onClick={() => {
                if (isEdit && module) setPickerOpen(true);
                else void onSaveAndAddChild();
              }}
            >
              <Plus className="size-4" />
              Añadir hijo
            </Button>
          </div>
          <ModulesHierarchyTable
            directChildren={module?.children ?? []}
            expandable
            emptyMessage="Sin hijos todavía."
            {...(isEdit && module
              ? {
                  onRemoveChild: (childId: string) =>
                    removeChild.mutate({ id: module.id, childId }),
                }
              : {})}
          />
        </section>
      </form>

      {isEdit && module && (
        <AddChildModal
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          parentId={module.id}
          parentLabel={module.name}
          existingChildren={module.children}
          onConfirm={async (input) => {
            await addChild.mutateAsync({
              id: module.id,
              payload: {
                ...(input.child_module_id
                  ? { child_module_id: input.child_module_id }
                  : { child_component_id: input.child_component_id! }),
                quantity: input.quantity,
              },
            });
          }}
        />
      )}
    </DashboardLayout>
  );
}

const inputCls =
  "h-10 w-full rounded-md border border-border bg-white px-3 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";

interface FormFieldProps {
  label: string;
  icon?: ReactNode | undefined;
  error?: string | undefined;
  children: React.ReactNode;
}

function FormField({ label, icon, error, children }: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
        {icon && <span className="text-text-secondary">{icon}</span>}
        {label}
      </label>
      {children}
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function ReadonlyField({
  icon,
  label,
  value,
}: {
  icon?: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-text-secondary">
        {icon && <span className="text-text-secondary/70">{icon}</span>}
        {label}
      </span>
      <span className="text-sm font-medium text-text-primary">{value}</span>
    </div>
  );
}
