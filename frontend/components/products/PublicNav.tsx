import Link from "next/link";
import Image from "next/image";

/**
 * Shared header for public routes (/, /products, /products/[id], /privacy,
 * /terms). Keeps the two auth CTAs consistent everywhere without touching
 * each page.
 */
export function PublicNav() {
  return (
    <header className="flex items-center justify-between enter">
      <Link href="/" className="flex items-center">
        <Image
          src="/brand/logo.png"
          alt="Corridor One X"
          width={1998}
          height={320}
          priority
          className="h-6 w-auto select-none sm:h-7"
        />
      </Link>
      <div className="flex items-center gap-3 text-xs">
        <Link
          href="/products"
          className="text-paper-muted transition-colors hover:text-paper"
        >
          Catalog
        </Link>
        <Link
          href="/login"
          className="rounded-full border border-line-soft px-3 py-1.5 text-paper-muted transition-colors hover:text-paper"
        >
          Sign in
        </Link>
        <Link
          href="/signup"
          className="rounded-full bg-accent px-3 py-1.5 font-medium text-accent-fg hover:bg-accent-hover"
        >
          Get started
        </Link>
      </div>
    </header>
  );
}
