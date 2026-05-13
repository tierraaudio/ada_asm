import { zodResolver } from "@hookform/resolvers/zod";
import { Mail } from "lucide-react";
import { type FC, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { authApi } from "../api/auth-api";
import { BrandWordmark } from "../components/BrandWordmark";
import { forgotPasswordSchema, type ForgotPasswordInput } from "../schemas";

export const ForgotPasswordPage: FC = () => {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordInput>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await authApi.requestPasswordRecovery(values.email);
    } catch {
      /* The endpoint always returns 202; any thrown error is a transport
         failure and we still want to show the neutral confirmation so the
         UI does not reveal account existence. */
    }
    setSubmitted(true);
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-page-bg p-4">
      <div className="flex w-full max-w-[448px] flex-col gap-8">
        <header>
          <BrandWordmark />
          <h1 className="mt-6 text-center text-2xl font-medium leading-9 text-text-primary">
            Recuperar contraseña
          </h1>
          <p className="mt-2 text-center text-base leading-6 text-text-secondary">
            Te enviaremos un enlace para restablecer tu contraseña
          </p>
        </header>

        <section className="rounded-lg border border-border bg-white p-[33px] shadow-[0px_1px_1.5px_rgba(0,0,0,0.1),0px_1px_1px_rgba(0,0,0,0.1)]">
          {submitted ? (
            <div className="flex flex-col gap-4 text-center">
              <p className="text-base text-text-primary">
                Si existe una cuenta para ese email, te llegará un enlace para restablecer tu
                contraseña en breve.
              </p>
              <Link
                to="/login"
                className="text-sm text-brand hover:underline focus-visible:underline focus-visible:outline-none"
              >
                Volver al inicio de sesión
              </Link>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-label="Forgot password">
              <div className="flex flex-col gap-2">
                <label
                  htmlFor="forgot-email"
                  className="text-base font-medium leading-6 text-text-primary"
                >
                  Email
                </label>
                <div className="relative">
                  <Mail
                    className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-text-secondary"
                    aria-hidden="true"
                  />
                  <input
                    id="forgot-email"
                    type="email"
                    autoComplete="email"
                    placeholder="tu@email.com"
                    className="h-[42px] w-full rounded-md border border-border bg-white pl-10 pr-4 text-base text-text-primary placeholder:text-text-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                    aria-invalid={errors.email ? "true" : "false"}
                    {...register("email")}
                  />
                </div>
                {errors.email && (
                  <p role="alert" className="text-sm text-destructive">
                    {errors.email.message}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="h-11 w-full rounded-md bg-brand text-base font-medium text-brand-foreground transition-colors hover:bg-brand/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Enviando…" : "Enviar enlace"}
              </button>

              <Link
                to="/login"
                className="text-center text-sm text-text-secondary hover:underline focus-visible:underline focus-visible:outline-none"
              >
                Volver al inicio de sesión
              </Link>
            </form>
          )}
        </section>
      </div>
    </div>
  );
};
