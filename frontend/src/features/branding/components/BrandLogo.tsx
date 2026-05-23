import type { FC, ImgHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/**
 * Singular Things wordmark — pulled from the SVG at
 * `public/brand/singularthings-wordmark.svg` (Vite serves it from `/brand/...`).
 *
 * Used by the authenticated dashboard sidebar. The auth pages continue to
 * use the larger text-based `BrandWordmark` until / unless a future design
 * migrates them too.
 */
type BrandLogoProps = Omit<ImgHTMLAttributes<HTMLImageElement>, "src" | "alt">;

export const BrandLogo: FC<BrandLogoProps> = ({
  className,
  width = 128,
  height = 28,
  ...props
}) => {
  return (
    <img
      src="/brand/singularthings-wordmark.svg"
      alt="Singular Things"
      width={width}
      height={height}
      decoding="async"
      loading="eager"
      className={cn("block h-auto select-none", className)}
      {...props}
    />
  );
};
