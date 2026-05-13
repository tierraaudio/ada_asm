import type { FC } from "react";

/**
 * The "singularthings" wordmark from Figma 37:2 — "singular" in #1a1a1a +
 * "things" in brand magenta. Rendered as a single h1 line at 40 px / 60 px.
 */
export const BrandWordmark: FC = () => {
  return (
    <p
      aria-label="singularthings"
      className="text-center font-sans text-[40px] font-black leading-[60px] tracking-[-0.6289px] text-text-primary"
    >
      <span>singular</span>
      <span className="text-brand">things</span>
    </p>
  );
};
