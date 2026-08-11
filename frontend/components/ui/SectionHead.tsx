import { ReactNode } from "react";

export function SectionHead({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <h3 className="section-head">
      <span aria-hidden className="inline-flex">
        {icon}
      </span>
      {children}
    </h3>
  );
}
