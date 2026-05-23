import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { type FC, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/auth-api";
import { BrandWordmark } from "../components/BrandWordmark";
import { resetPasswordSchema, type ResetPasswordInput } from "../schemas";

export const ResetPasswordPage: FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordInput>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    if (!token) return;
    try {
      await authApi.resetPassword(token, values.new_password);
      navigate("/login?reset=success", { replace: true });
    } catch (err) {
      if (isAxiosError(err)) {
        const code = err.response?.data?.code;
        if (
          code === "RESET_TOKEN_EXPIRED" ||
          code === "RESET_TOKEN_ALREADY_USED" ||
          code === "RESET_TOKEN_INVALID"
        ) {
          setSubmitError(
            "El enlace ya no es válido. Solicita uno nuevo desde 'Recuperar contraseña'.",
          );
          return;
        }
        if (code === "PASSWORD_TOO_SHORT") {
          setSubmitError("La contraseña debe tener al menos 12 caracteres.");
          return;
        }
      }
      setSubmitError("No se ha podido restablecer la contraseña. Inténtalo de nuevo.");
    }
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-page-bg p-4">
      <div className="flex w-full max-w-[448px] flex-col gap-8">
        <header>
          <BrandWordmark />
          <h1 className="mt-6 text-center text-2xl font-medium leading-9 text-text-primary">
            Nueva contraseña
          </h1>
        </header>

        <section className="rounded-lg border border-border bg-white p-[33px] shadow-[0px_1px_1.5px_rgba(0,0,0,0.1),0px_1px_1px_rgba(0,0,0,0.1)]">
          {!token ? (
            <div className="flex flex-col gap-4 text-center">
              <p role="alert" className="text-sm text-destructive">
                El enlace de recuperación no es válido o ha caducado.
              </p>
              <Link
                to="/forgot-password"
                className="text-sm text-brand hover:underline focus-visible:underline focus-visible:outline-none"
              >
                Solicitar un nuevo enlace
              </Link>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-label="Reset password">
              <div className="flex flex-col gap-2">
                <label
                  htmlFor="new-password"
                  className="text-base font-medium leading-6 text-text-primary"
                >
                  Nueva contraseña
                </label>
                <input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  className="h-[42px] w-full rounded-md border border-border bg-white px-4 text-base text-text-primary placeholder:text-text-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                  {...register("new_password")}
                />
                {errors.new_password && (
                  <p role="alert" className="text-sm text-destructive">
                    {errors.new_password.message}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <label
                  htmlFor="confirm-password"
                  className="text-base font-medium leading-6 text-text-primary"
                >
                  Confirmar contraseña
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  className="h-[42px] w-full rounded-md border border-border bg-white px-4 text-base text-text-primary placeholder:text-text-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                  {...register("confirm_password")}
                />
                {errors.confirm_password && (
                  <p role="alert" className="text-sm text-destructive">
                    {errors.confirm_password.message}
                  </p>
                )}
              </div>

              {submitError && (
                <p
                  role="alert"
                  className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
                >
                  {submitError}
                </p>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="h-11 w-full rounded-md bg-brand text-base font-medium text-brand-foreground transition-colors hover:bg-brand/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Guardando…" : "Guardar contraseña"}
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  );
};
