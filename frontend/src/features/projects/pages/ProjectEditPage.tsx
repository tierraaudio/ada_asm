import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { Calendar, Plus, Save } from "lucide-react";
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
import { AddChildModal } from "@/features/modules/components/AddChildModal";
import { ModulesHierarchyTable } from "@/features/modules/components/ModulesHierarchyTable";
import { useDetailNavPush } from "@/features/shared/nav/DetailNavControls";
import { useDetailNavStack } from "@/features/shared/nav/DetailNavStack";
import { DetailPageHeader } from "@/features/shared/nav/DetailPageHeader";
import { cn } from "@/lib/utils/cn";

import { CreateCustomerModal } from "../components/CreateCustomerModal";
import { EmojiPicker } from "../components/EmojiPicker";
import { InterestLinksField } from "../components/InterestLinksField";
import { useCustomers } from "../hooks/use-customers";
import { useProjectDetail } from "../hooks/use-project-detail";
import {
  useAddInterestLink,
  useAddProjectChild,
  useCreateProject,
  useRemoveInterestLink,
  useRemoveProjectChild,
  useUpdateInterestLink,
  useUpdateProject,
} from "../hooks/use-project-mutations";
import { PROJECT_STATUS_VALUES, type Customer, type ProjectStatus } from "../types";

function formatDdMmYyyy(iso: string | null | undefined): string {
  if (!iso) return "—";
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

interface ProjectEditPageProps {
  mode: "create" | "edit";
}

const formSchema = z.object({
  code: z.string().trim().min(1, "Clave obligatoria").max(40),
  name: z.string().trim().min(1, "Nombre obligatorio").max(200),
  description: z.string().optional(),
  status: z
    .string()
    .min(1, "Estado obligatorio")
    .refine(
      (v) => (PROJECT_STATUS_VALUES as readonly string[]).includes(v),
      "Estado inválido",
    ),
  customer_id: z.string().optional(),
  icon: z.string().max(8).optional(),
  color: z
    .string()
    .optional()
    .refine(
      (v) => !v || /^#[0-9a-fA-F]{6}$/.test(v),
      "Color debe ser un hex `#rrggbb`",
    ),
  tags_input: z.string().optional(),
  version: z.string().max(40).optional(),
  fecha_inicio: z.string().optional(),
  fecha_entrega_estimada: z.string().optional(),
  fecha_entrega_real: z.string().optional(),
  notas: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

const EMPTY_DEFAULTS: FormValues = {
  code: "",
  name: "",
  description: "",
  status: "Presupuestado",
  customer_id: "",
  icon: "",
  color: "",
  tags_input: "",
  version: "",
  fecha_inicio: "",
  fecha_entrega_estimada: "",
  fecha_entrega_real: "",
  notas: "",
};

function tagsFromInput(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

function tagsToInput(tags: string[]): string {
  return tags.join(", ");
}

export function ProjectEditPage({ mode }: ProjectEditPageProps) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const isEdit = mode === "edit";
  const [pickerOpen, setPickerOpen] = useState(false);
  const [createCustomerOpen, setCreateCustomerOpen] = useState(false);
  const { reset: resetNavStack } = useDetailNavStack();
  useDetailNavPush();

  const detailQuery = useProjectDetail(isEdit ? id : undefined);
  const customersQuery = useCustomers();
  const create = useCreateProject();
  const update = useUpdateProject();
  const addChild = useAddProjectChild();
  const removeChild = useRemoveProjectChild();
  const addInterestLink = useAddInterestLink();
  const updateInterestLink = useUpdateInterestLink();
  const removeInterestLink = useRemoveInterestLink();

  const {
    register,
    handleSubmit,
    reset,
    control,
    watch,
    setValue,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: EMPTY_DEFAULTS,
  });

  const currentStatus = watch("status");

  useEffect(() => {
    if (!isEdit || !detailQuery.data) return;
    const p = detailQuery.data;
    reset({
      code: p.code,
      name: p.name,
      description: p.description ?? "",
      status: p.status,
      customer_id: p.customer_id ?? "",
      icon: p.icon ?? "",
      color: p.color ?? "",
      tags_input: tagsToInput(p.tags ?? []),
      version: p.version ?? "",
      fecha_inicio: p.fecha_inicio ?? "",
      fecha_entrega_estimada: p.fecha_entrega_estimada ?? "",
      fecha_entrega_real: p.fecha_entrega_real ?? "",
      notas: p.notas ?? "",
    });
  }, [isEdit, detailQuery.data, reset]);

  const onCancel = () => {
    if (isEdit && id) navigate(`/projects/${id}`);
    else navigate("/projects");
  };

  const onClose = () => {
    resetNavStack();
    navigate("/projects");
  };

  const submitWith = (afterCreate: "detail" | "edit_open_picker") =>
    handleSubmit(async (values) => {
      const payload: Record<string, unknown> = {
        code: values.code.trim(),
        name: values.name.trim(),
        description: values.description?.trim() ? values.description.trim() : null,
        status: values.status as ProjectStatus,
        customer_id: values.customer_id?.trim() ? values.customer_id.trim() : null,
        icon: values.icon?.trim() ? values.icon.trim() : null,
        color: values.color?.trim() ? values.color.trim() : null,
        tags: tagsFromInput(values.tags_input),
        version: values.version?.trim() ? values.version.trim() : null,
        fecha_inicio: values.fecha_inicio?.trim() ? values.fecha_inicio.trim() : null,
        fecha_entrega_estimada: values.fecha_entrega_estimada?.trim()
          ? values.fecha_entrega_estimada.trim()
          : null,
        fecha_entrega_real: values.fecha_entrega_real?.trim()
          ? values.fecha_entrega_real.trim()
          : null,
        notas: values.notas?.trim() ? values.notas.trim() : null,
      };
      try {
        if (isEdit && id) {
          await update.mutateAsync({ id, payload: payload as Record<string, never> });
          if (afterCreate === "edit_open_picker") setPickerOpen(true);
          else navigate(`/projects/${id}`);
        } else {
          const created = await create.mutateAsync(
            payload as unknown as { code: string; name: string },
          );
          if (afterCreate === "edit_open_picker") {
            navigate(`/projects/${created.id}/edit?add_child=1`);
          } else {
            navigate(`/projects/${created.id}`);
          }
        }
      } catch (err) {
        console.error(err);
      }
    });

  const onSubmit = submitWith("detail");
  const onSaveAndAddChild = submitWith("edit_open_picker");

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
      ? "Ya existe un proyecto con ese código."
      : update.error
        ? "No se pudo guardar. Inténtalo de nuevo."
        : null;

  if (isEdit && id && detailQuery.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando proyecto…</p>
      </DashboardLayout>
    );
  }
  if (isEdit && (detailQuery.isError || (id && !detailQuery.data))) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el proyecto.</p>
      </DashboardLayout>
    );
  }

  const project = detailQuery.data;

  return (
    <DashboardLayout>
      <form
        noValidate
        onSubmit={onSubmit}
        className="mx-auto flex w-full max-w-[1920px] flex-col gap-6"
        aria-label={isEdit ? "Editar proyecto" : "Nuevo proyecto"}
      >
        <DetailPageHeader
          closeTo="/projects"
          onClose={onClose}
          rightSlot={
            <>
              <Button type="button" variant="outline" size="sm" onClick={onCancel}>
                Cancelar
              </Button>
              <Button type="submit" size="sm" disabled={isSubmitting || (isEdit && !isDirty)}>
                <Save className="size-4" />
                {isEdit ? "Guardar cambios" : "Crear proyecto"}
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
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_440px]">
            <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
            <FormField label="Código" error={errors.code?.message}>
              <input
                {...register("code")}
                type="text"
                className={inputCls}
                placeholder="PRY-2026-001"
              />
            </FormField>
            <FormField label="Estado" error={errors.status?.message}>
              <Controller
                control={control}
                name="status"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={(v) => field.onChange(v)}>
                    <SelectTrigger className={inputCls}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PROJECT_STATUS_VALUES.map((v) => (
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

          <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-3">
            <FormField
              label="Icono (emoji)"
              error={errors.icon?.message}
              hint="Elige uno de la paleta o pega cualquier emoji a mano."
            >
              <Controller
                control={control}
                name="icon"
                render={({ field }) => (
                  <div className="flex items-center gap-2">
                    <EmojiPicker
                      value={field.value}
                      onChange={(v) => field.onChange(v)}
                    />
                    <input
                      type="text"
                      value={field.value ?? ""}
                      onChange={(e) => field.onChange(e.target.value)}
                      className={cn(inputCls, "flex-1")}
                      placeholder="⚡"
                      maxLength={8}
                    />
                  </div>
                )}
              />
            </FormField>
            <FormField
              label="Color (hex)"
              error={errors.color?.message}
              hint="Formato #rrggbb. Se usa como acento en la lista y el header."
            >
              <Controller
                control={control}
                name="color"
                render={({ field }) => (
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={field.value && /^#[0-9a-fA-F]{6}$/.test(field.value)
                        ? field.value
                        : "#10b981"}
                      onChange={(e) => field.onChange(e.target.value)}
                      className="h-10 w-12 cursor-pointer rounded-md border border-border bg-white"
                      aria-label="Selector de color"
                    />
                    <input
                      type="text"
                      value={field.value ?? ""}
                      onChange={(e) => field.onChange(e.target.value)}
                      placeholder="#10b981"
                      className={cn(inputCls, "flex-1 font-mono")}
                    />
                  </div>
                )}
              />
            </FormField>
            <FormField label="Versión" error={errors.version?.message}>
              <input
                {...register("version")}
                type="text"
                className={inputCls}
                placeholder="v1.0"
                maxLength={40}
              />
            </FormField>
          </div>

          <div className="mt-4">
            <FormField label="Nombre" error={errors.name?.message}>
              <input
                {...register("name")}
                type="text"
                className={inputCls}
                placeholder="Sensor Ambiental ACME — Piloto"
              />
            </FormField>
          </div>

          <div className="mt-4">
            <FormField label="Descripción" error={errors.description?.message}>
              <textarea
                {...register("description")}
                rows={3}
                className={cn(inputCls, "min-h-[80px] resize-y")}
              />
            </FormField>
          </div>

          {isEdit && project && (
            <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-border pt-4 md:grid-cols-4">
              <ReadonlyField
                icon={<Calendar className="size-3.5" />}
                label="Fecha de creación"
                value={formatDdMmYyyy(project.created_at)}
              />
              <ReadonlyField
                icon={<Calendar className="size-3.5" />}
                label="Última modificación"
                value={formatDdMmYyyy(project.updated_at)}
              />
            </div>
          )}

          <div
            className={cn(
              "mt-4 grid grid-cols-1 gap-x-6 gap-y-4",
              currentStatus === "Completado" ? "md:grid-cols-3" : "md:grid-cols-2",
            )}
          >
            <FormField label="Fecha de inicio" error={errors.fecha_inicio?.message}>
              <input {...register("fecha_inicio")} type="date" className={inputCls} />
            </FormField>
            <FormField
              label="Fecha de vencimiento"
              error={errors.fecha_entrega_estimada?.message}
            >
              <input
                {...register("fecha_entrega_estimada")}
                type="date"
                className={inputCls}
              />
            </FormField>
            {currentStatus === "Completado" && (
              <FormField label="Entrega real" error={errors.fecha_entrega_real?.message}>
                <input
                  {...register("fecha_entrega_real")}
                  type="date"
                  className={inputCls}
                />
              </FormField>
            )}
          </div>

          <div className="mt-4">
            <FormField label="Cliente" error={errors.customer_id?.message}>
              <div className="flex items-center gap-2">
                <Controller
                  control={control}
                  name="customer_id"
                  render={({ field }) => (
                    <Select
                      value={field.value ? field.value : "__none__"}
                      onValueChange={(v) => field.onChange(v === "__none__" ? "" : v)}
                    >
                      <SelectTrigger className={cn(inputCls, "flex-1")}>
                        <SelectValue placeholder="Selecciona cliente…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">—</SelectItem>
                        {(customersQuery.data ?? []).map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.name} ({c.holded_id})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCreateCustomerOpen(true)}
                >
                  <Plus className="size-4" />
                  Nuevo cliente
                </Button>
              </div>
            </FormField>
          </div>

          <div className="mt-4">
            <FormField
              label="Tags"
              error={errors.tags_input?.message}
              hint="Coma-separados (ej. `power, motor, automotive, alta-corriente`)."
            >
              <input
                {...register("tags_input")}
                type="text"
                className={inputCls}
                placeholder="power, motor, automotive"
              />
            </FormField>
          </div>

          <div className="mt-4">
            <FormField label="Notas" error={errors.notas?.message}>
              <textarea
                {...register("notas")}
                rows={3}
                className={cn(inputCls, "min-h-[80px] resize-y")}
              />
            </FormField>
          </div>
            </div>

            {/* Right column — Enlaces de interés (Figma-aligned) */}
            <div>
              <InterestLinksField
                links={isEdit && project ? project.interest_links : []}
                disabled={!isEdit || !project}
                onAdd={
                  isEdit && project
                    ? async (payload) => {
                        await addInterestLink.mutateAsync({
                          id: project.id,
                          payload: {
                            name: payload.name,
                            url: payload.url,
                            sort_order: project.interest_links.length,
                          },
                        });
                      }
                    : undefined
                }
                onEdit={
                  isEdit && project
                    ? async (linkId, payload) => {
                        await updateInterestLink.mutateAsync({
                          id: project.id,
                          linkId,
                          payload,
                        });
                      }
                    : undefined
                }
                onRemove={
                  isEdit && project
                    ? async (linkId) => {
                        await removeInterestLink.mutateAsync({
                          id: project.id,
                          linkId,
                        });
                      }
                    : undefined
                }
              />
            </div>
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
                if (isEdit && project) setPickerOpen(true);
                else void onSaveAndAddChild();
              }}
            >
              <Plus className="size-4" />
              Añadir hijo
            </Button>
          </div>
          <ModulesHierarchyTable
            directChildren={project?.children ?? []}
            expandable
            emptyMessage="Sin hijos todavía."
            {...(isEdit && project
              ? {
                  onRemoveChild: (childId: string) =>
                    removeChild.mutate({ id: project.id, childId }),
                }
              : {})}
          />
        </section>
      </form>

      {isEdit && project && (
        <AddChildModal
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          parentId={project.id}
          parentLabel={project.name}
          existingChildren={project.children}
          onConfirm={async (input) => {
            await addChild.mutateAsync({
              id: project.id,
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

      <CreateCustomerModal
        open={createCustomerOpen}
        onOpenChange={setCreateCustomerOpen}
        onCreated={(customer: Customer) => {
          setValue("customer_id", customer.id, { shouldDirty: true });
        }}
      />
    </DashboardLayout>
  );
}

const inputCls =
  "h-10 w-full rounded-md border border-border bg-white px-3 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";

interface FormFieldProps {
  label: string;
  icon?: ReactNode | undefined;
  error?: string | undefined;
  hint?: string | undefined;
  children: React.ReactNode;
}

function FormField({ label, icon, error, hint, children }: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
        {icon && <span className="text-text-secondary">{icon}</span>}
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-text-secondary">{hint}</p>}
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
