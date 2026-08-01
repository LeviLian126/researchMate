// Renders the approved ResearchMate brand mark with an optional wordmark.
import Image from "next/image";
import logoMark from "../../public/researchmate-logo-mark.png";

/** Displays the native-resolution navy and blue mark cropped from approved option 05. */
export function BrandLogo({ withName = false }: { withName?: boolean }) {
  return (
    <span className={`brand-logo ${withName ? "brand-logo--named" : ""}`}>
      <span className="brand-logo__crop" aria-hidden="true">
        <Image src={logoMark} alt="" priority unoptimized />
      </span>
      {withName && <strong>ResearchMate</strong>}
    </span>
  );
}
