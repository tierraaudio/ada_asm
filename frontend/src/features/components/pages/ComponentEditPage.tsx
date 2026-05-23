import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { Controller, useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

import { CountryOfOriginSelect } from "../components/CountryOfOriginSelect";
import { NatoScoreBadge } from "../components/NatoScoreBadge";
import { TierBadge } from "../components/TierBadge";
import { useComponent } from "../hooks/use-component";
import {
  useCreateComponent,
  useUpdateComponent,
} from "../hooks/use-component-mutations";
import { NATO_SCORE_LABELS, TIER_LABELS } from "../rubrics";
import {
  componentCreateSchema,
  componentUpdateSchema,
  type ComponentCreateInput,
  type ComponentUpdateInput,
} from "../schemas";
import { NATO_SCORE_VALUES, TIER_VALUES } from "../types";
import type { NatoScoreValue, TierValue } from "../types";

interface ComponentEditPageProps {
  mode: "create" | "edit";
}

const FIELD_CLASS =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";

export function ComponentEditPage({ mode }: ComponentEditPageProps) {
  return mode === "create" ? <CreateComponentForm /> : <EditComponentForm />;
}

function CreateComponentForm() {
  const navigate = useNavigate();
  const mutation = useCreateComponent();
  const form = useForm<ComponentCreateInput>({
    resolver: zodResolver(componentCreateSchema),
    defaultValues: {
      mpn: "",
      name: "",
      family: "",
      sku: "",
      description: "",
      datasheet_url: "",
      location: "",
      supplier: "",
      price_per_100: "",
      stock: 0,
      tier: "C",
      nato_score: "neutral",
      country_of_origin: "",
    },
  });

  async function onSubmit(values: ComponentCreateInput) {
    try {
      const created = await mutation.mutateAsync(
        componentCreateSchema.parse(values),
      );
      navigate(`/components/${created.id}`);
    } catch (err) {
      handleServerErrors(err, form.setError);
    }
  }

  return (
    <FormShell
      title="Nuevo componente"
      onSubmit={form.handleSubmit(onSubmit)}
      onCancel={() => navigate("/components")}
      submitLabel="Crear componente"
      isSubmitting={mutation.isPending}
    >
      <ComponentFormBody mode="create" form={form} />
    </FormShell>
  );
}

function EditComponentForm() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const componentQuery = useComponent(id);
  const mutation = useUpdateComponent(id ?? "");

  const baseValues: ComponentUpdateInput | undefined = componentQuery.data
    ? {
        name: componentQuery.data.name,
        family: componentQuery.data.family,
        sku: componentQuery.data.sku ?? "",
        description: componentQuery.data.description ?? "",
        datasheet_url: componentQuery.data.datasheet_url ?? "",
        location: componentQuery.data.location ?? "",
        supplier: componentQuery.data.supplier ?? "",
        price_per_100: componentQuery.data.price_per_100 ?? "",
        stock: componentQuery.data.stock,
        tier: componentQuery.data.tier,
        nato_score: componentQuery.data.nato_score,
        country_of_origin: componentQuery.data.country_of_origin ?? "",
      }
    : undefined;

  const form = useForm<ComponentUpdateInput>(
    baseValues
      ? { resolver: zodResolver(componentUpdateSchema), values: baseValues }
      : { resolver: zodResolver(componentUpdateSchema) },
  );

  if (!id || componentQuery.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando componente…</p>
      </DashboardLayout>
    );
  }
  if (!componentQuery.data) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el componente.</p>
      </DashboardLayout>
    );
  }

  async function onSubmit(values: ComponentUpdateInput) {
    try {
      await mutation.mutateAsync(componentUpdateSchema.parse(values));
      navigate(`/components/${id}`);
    } catch (err) {
      handleServerErrors(err, form.setError);
    }
  }

  return (
    <FormShell
      title={`Editar ${componentQuery.data.mpn}`}
      onSubmit={form.handleSubmit(onSubmit)}
      onCancel={() => navigate(`/components/${id}`)}
      submitLabel="Guardar cambios"
      isSubmitting={mutation.isPending}
    >
      <ComponentFormBody
        mode="edit"
        form={form}
        readOnlyMpn={componentQuery.data.mpn}
      />
    </FormShell>
  );
}

interface FormShellProps {
  title: string;
  onSubmit: React.FormEventHandler<HTMLFormElement>;
  onCancel: () => void;
  submitLabel: string;
  isSubmitting: boolean;
  children: React.ReactNode;
}

function FormShell({
  title,
  onSubmit,
  onCancel,
  submitLabel,
  isSubmitting,
  children,
}: FormShellProps) {
  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancelar
          </Button>
        </header>
        <form
          onSubmit={onSubmit}
          className="rounded-lg border border-border bg-white p-6 shadow-sm"
        >
          {children}
          <div className="mt-6 flex items-center justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Guardando…" : submitLabel}
            </Button>
          </div>
        </form>
      </div>
    </DashboardLayout>
  );
}

interface ComponentFormBodyProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: any;
  mode: "create" | "edit";
  readOnlyMpn?: string;
}

function ComponentFormBody({ form, mode, readOnlyMpn }: ComponentFormBodyProps) {
  const {
    register,
    control,
    formState: { errors },
  } = form;

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <Field label="MPN" error={errors.mpn?.message} required={mode === "create"}>
        {mode === "create" ? (
          <input
            type="text"
            className={cn(FIELD_CLASS, "font-mono")}
            {...register("mpn")}
          />
        ) : (
          <input
            type="text"
            value={readOnlyMpn ?? ""}
            readOnly
            className={cn(FIELD_CLASS, "cursor-not-allowed bg-muted font-mono")}
          />
        )}
      </Field>
      <Field label="SKU" error={errors.sku?.message}>
        <input type="text" className={FIELD_CLASS} {...register("sku")} />
      </Field>
      <Field label="Nombre" error={errors.name?.message} required>
        <input type="text" className={FIELD_CLASS} {...register("name")} />
      </Field>
      <Field label="Familia" error={errors.family?.message} required>
        <input type="text" className={FIELD_CLASS} {...register("family")} />
      </Field>
      <Field
        label="Descripción"
        error={errors.description?.message}
        className="md:col-span-2"
      >
        <textarea
          rows={3}
          className={cn(FIELD_CLASS, "h-auto min-h-[5rem] py-2")}
          {...register("description")}
        />
      </Field>
      <Field
        label="Datasheet URL"
        error={errors.datasheet_url?.message}
        className="md:col-span-2"
      >
        <input
          type="url"
          placeholder="https://…"
          className={FIELD_CLASS}
          {...register("datasheet_url")}
        />
      </Field>
      <Field label="Ubicación" error={errors.location?.message}>
        <input type="text" className={FIELD_CLASS} {...register("location")} />
      </Field>
      <Field label="Supplier" error={errors.supplier?.message}>
        <input type="text" className={FIELD_CLASS} {...register("supplier")} />
      </Field>
      <Field label="Precio (100u, €)" error={errors.price_per_100?.message}>
        <input
          type="text"
          inputMode="decimal"
          placeholder="0.0000"
          className={FIELD_CLASS}
          {...register("price_per_100")}
        />
      </Field>
      <Field label="Stock" error={errors.stock?.message}>
        <input
          type="number"
          min={0}
          step={1}
          className={FIELD_CLASS}
          {...register("stock", { valueAsNumber: true })}
        />
      </Field>
      <Field label="Tier" error={errors.tier?.message} required>
        <Controller
          control={control}
          name="tier"
          render={({ field }) => (
            <div className="flex items-center gap-2">
              <select
                className={FIELD_CLASS}
                value={field.value ?? "C"}
                onChange={(e) => field.onChange(e.target.value as TierValue)}
              >
                {TIER_VALUES.map((t) => (
                  <option key={t} value={t}>
                    {TIER_LABELS[t]}
                  </option>
                ))}
              </select>
              {field.value && <TierBadge value={field.value as TierValue} />}
            </div>
          )}
        />
      </Field>
      <Field label="Scoring OTAN" error={errors.nato_score?.message} required>
        <Controller
          control={control}
          name="nato_score"
          render={({ field }) => (
            <div className="flex items-center gap-2">
              <select
                className={FIELD_CLASS}
                value={field.value ?? "neutral"}
                onChange={(e) =>
                  field.onChange(e.target.value as NatoScoreValue)
                }
              >
                {NATO_SCORE_VALUES.map((s) => (
                  <option key={s} value={s}>
                    {NATO_SCORE_LABELS[s]}
                  </option>
                ))}
              </select>
              {field.value && (
                <NatoScoreBadge value={field.value as NatoScoreValue} />
              )}
            </div>
          )}
        />
      </Field>
      <Field
        label="País de origen"
        error={errors.country_of_origin?.message}
        className="md:col-span-2"
      >
        <Controller
          control={control}
          name="country_of_origin"
          render={({ field }) => (
            <CountryOfOriginSelect
              value={field.value as string | null | undefined}
              onChange={field.onChange}
            />
          )}
        />
      </Field>
    </div>
  );
}

function Field({
  label,
  error,
  required,
  className,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  // Wrap children inside <label> so RTL's getByLabelText can resolve the
  // implicit association without needing an id + htmlFor for every field.
  return (
    <label className={cn("flex flex-col gap-1.5", className)}>
      <span className="text-sm font-medium text-text-primary">
        {label}
        {required && <span className="ml-1 text-destructive">*</span>}
      </span>
      {children}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </label>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleServerErrors(err: unknown, setError: any) {
  if (!isAxiosError(err)) throw err;
  const data = err.response?.data as
    | { code?: string; errors?: Array<{ loc?: (string | number)[]; msg?: string }> }
    | undefined;
  if (data?.code === "MPN_ALREADY_REGISTERED") {
    setError("mpn", { type: "server", message: "Ya existe un componente con ese MPN." });
    return;
  }
  if (data?.code === "VALIDATION_ERROR" && Array.isArray(data.errors)) {
    for (const issue of data.errors) {
      const field = String(issue.loc?.[issue.loc.length - 1] ?? "");
      if (field) {
        setError(field, { type: "server", message: issue.msg ?? "Inválido" });
      }
    }
    return;
  }
  setError("root", {
    type: "server",
    message: "No se pudo guardar el componente. Inténtalo de nuevo.",
  });
}
