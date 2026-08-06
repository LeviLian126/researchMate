import { cn } from "@/lib/utils";
import { brandConfig } from "@/lib/types";

interface BrandLogoProps {
  showWordmark?: boolean;
  className?: string;
}

export function BrandLogo({ showWordmark = true, className }: BrandLogoProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="relative flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/85 shadow-md shadow-primary/30 ring-1 ring-inset ring-white/25">
        <span className="font-serif text-lg font-semibold leading-none text-primary-foreground">
          {brandConfig.mark}
        </span>
      </div>
      {showWordmark && (
        <span className="text-[15px] font-semibold tracking-tight text-foreground">
          {brandConfig.name}
        </span>
      )}
    </div>
  );
}
