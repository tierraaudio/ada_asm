import type { FC } from "react";

export const Header: FC = () => {
  return (
    <header
      role="banner"
      data-testid="app-header"
      className="flex h-16 items-center border-b border-border bg-background px-6"
    >
      <h1 className="text-lg font-semibold text-foreground">ADA ASM</h1>
    </header>
  );
};
