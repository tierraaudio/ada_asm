import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { Lock, Mail } from "lucide-react";
import { type FC, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/auth-api";
import { BrandWordmark } from "../components/BrandWordmark";
import { loginSchema, type LoginInput } from "../schemas";
import { useAuthStore } from "@/lib/stores/auth-store";
import { writeRefreshToken } from "@/lib/auth/token-storage";

export const LoginPage: FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const setSession = useAuthStore((s) => s.setSession);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    resetField,
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      const tokens = await authApi.login(values.email, values.password);
      writeRefreshToken(tokens.refresh_token);
      useAuthStore.setState({ accessToken: tokens.access_token });
      const me = await authApi.getMe();
      setSession(tokens.access_token, me);
      const next = searchParams.get("next") ?? "/";
      navigate(next, { replace: true });
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) {
        setSubmitError("El email o la contraseña no son correctos");
      } else {
        setSubmitError(
          "No se ha podido iniciar sesión. Inténtalo de nuevo en unos segundos.",
        );
      }
      resetField("password");
    }
  });

  const isDev = import.meta.env.VITE_ENV === "development";

  return (
    <div className="flex min-h-screen items-center justify-center bg-page-bg p-4">
      <div className="flex w-full max-w-[448px] flex-col gap-8">
        <header className="flex flex-col gap-0">
          <BrandWordmark />
          <h1 className="mt-6 text-center text-2xl font-medium leading-9 tracking-[0.0703px] text-text-primary">
            ASM V2
          </h1>
          <p className="mt-[8px] text-center text-base leading-6 tracking-[-0.3125px] text-text-secondary">
            Ingresa tus credenciales para continuar
          </p>
        </header>

        <section className="rounded-lg border border-border bg-white p-[33px] pb-px shadow-[0px_1px_1.5px_rgba(0,0,0,0.1),0px_1px_1px_rgba(0,0,0,0.1)]">
          <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4" aria-label="Login">
            {/* Email */}
            <div className="flex flex-col gap-2">
              <label
                htmlFor="email"
                className="text-base font-medium leading-6 tracking-[-0.3125px] text-text-primary"
              >
                Email
              </label>
              <div className="relative">
                <Mail
                  className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-text-secondary"
                  aria-hidden="true"
                />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="tu@email.com"
                  className="h-[42px] w-full rounded-md border border-border bg-white pl-10 pr-4 text-base leading-normal tracking-[-0.3125px] text-text-primary placeholder:text-text-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
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

            {/* Password */}
            <div className="flex flex-col gap-2">
              <label
                htmlFor="password"
                className="text-base font-medium leading-6 tracking-[-0.3125px] text-text-primary"
              >
                Contraseña
              </label>
              <div className="relative">
                <Lock
                  className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-text-secondary"
                  aria-hidden="true"
                />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="h-[42px] w-full rounded-md border border-border bg-white pl-10 pr-4 text-base leading-normal tracking-[-0.3125px] text-text-primary placeholder:text-text-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                  aria-invalid={errors.password ? "true" : "false"}
                  {...register("password")}
                />
              </div>
              {errors.password && (
                <p role="alert" className="text-sm text-destructive">
                  {errors.password.message}
                </p>
              )}
            </div>

            <div className="flex items-center justify-end">
              <Link
                to="/forgot-password"
                className="text-sm leading-5 tracking-[-0.1504px] text-brand hover:underline focus-visible:underline focus-visible:outline-none"
              >
                ¿Olvidaste tu contraseña?
              </Link>
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
              className="h-11 w-full rounded-md bg-brand text-base font-medium leading-6 tracking-[-0.3125px] text-brand-foreground transition-colors hover:bg-brand/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Iniciando sesión…" : "Iniciar sesión"}
            </button>

            {isDev && (
              <div className="mt-2 flex flex-col items-center gap-2 border-t border-border py-6">
                <p className="text-sm leading-5 tracking-[-0.1504px] text-text-secondary">
                  Usuarios de prueba:
                </p>
                <code className="font-mono-code rounded-sm bg-code-bg px-3 py-1 text-center text-xs leading-4 text-text-secondary">
                  admin@singularthings.io / admin123
                </code>
              </div>
            )}
          </form>
        </section>
      </div>
    </div>
  );
};
