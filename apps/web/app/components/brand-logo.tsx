import Image from "next/image";
import logoGrid from "../../../../logo.png";

/** Displays the selected navy and blue option from the approved ResearchMate logo sheet. */
export function BrandLogo({ withName = false }: { withName?: boolean }) {
  return (
    <span className={`brand-logo ${withName ? "brand-logo--named" : ""}`}>
      <span className="brand-logo__crop" aria-hidden="true">
        <Image src={logoGrid} alt="" priority sizes="40px" />
      </span>
      {withName && <strong>ResearchMate</strong>}
    </span>
  );
}
