// Renders the approved ResearchMate brand mark with an optional wordmark.
import Image from "next/image";
import logoMark from "../../public/researchmate-logo-mark.png";

/** Displays the native-resolution navy and blue mark cropped from approved option 05. */
export function BrandLogo({ withName = false }: { withName?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center" aria-hidden="true">
        <Image src={logoMark} alt="" priority unoptimized />
      </span>
      {withName && (
        <strong className="text-[15px] font-semibold tracking-tight text-foreground">ResearchMate</strong>
      )}
    </span>
  );
}
