import Link from "next/link";
import { NightWordmark } from "@/components/shell/NightShell";
import { landingWrap } from "./SectionHead";

const LINKS = [
  { href: "/products", label: "Market" },
  { href: "/signup", label: "Get verified" },
  { href: "/login", label: "Sign in" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
] as const;

export function LandingFooter() {
  return (
    <footer className={`${landingWrap} pb-10 pt-24 sm:pt-32`}>
      <div className="flex flex-wrap items-start justify-between gap-8 border-t border-line pt-8">
        <div>
          <NightWordmark />
          <p className="t-sub mt-3 max-w-[36ch] text-fg-3">
            Verified commodity trade between India and the Gulf.
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-x-6 gap-y-3">
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="t-callout rounded-sm text-fg-2 transition-colors hover:text-cream">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      <p className="t-foot mt-10 text-fg-3">
        © {new Date().getFullYear()} Corridor One X · Verified trade infrastructure for India &amp; the Gulf
      </p>
    </footer>
  );
}
