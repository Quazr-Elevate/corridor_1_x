import { HeroShip } from "./HeroShip";

export function BrandHeader() {
  return (
    <header className="relative">
      <div className="flex items-start justify-between gap-3">
        <div className="pt-1">
          <div className="text-[2rem] font-extrabold leading-none tracking-[-0.03em] text-ink">
            Cor1x
          </div>
          <p className="mt-2 text-sm text-mute">Trade Direct. Settle Certain.</p>
        </div>
        <div className="w-[42%] max-w-[180px] shrink-0">
          <HeroShip className="h-auto w-full" />
        </div>
      </div>
    </header>
  );
}
