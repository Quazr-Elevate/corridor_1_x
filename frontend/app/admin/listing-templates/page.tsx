"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { adminApi, errorMessage } from "@/lib/adminApi";
import type { CertificateType, SpecParameter } from "@/lib/publicApi";
import { cn } from "@/lib/cn";
import { useTower } from "@/components/shell/TowerShell";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Checkbox } from "@/components/ui/Controls";
import { Input, Select } from "@/components/ui/Field";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { LaneHeader } from "@/components/admin/tower";
import { PRODUCT_CATEGORIES } from "@/components/products/ListingForm";

const OPERATORS = [
  { value: "MAX", label: "Maximum" },
  { value: "MIN", label: "Minimum" },
  { value: "EQ", label: "Exactly" },
];
const codeOf = (name: string) =>
  name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^(\d)/, "p$1").slice(0, 40);

/**
 * What a listing in each category is asked for: the specification rows and
 * the documents. Rows are retired, never deleted, because listings use them.
 */
export default function ListingTemplatesPage() {
  const toast = useToast();
  const { can } = useTower();
  const canManage = can("catalog.manage");
  const [category, setCategory] = useState<string>("Rice");
  const [specs, setSpecs] = useState<SpecParameter[] | null>(null);
  const [certs, setCerts] = useState<CertificateType[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async (cat: string) => {
    setError(null);
    try {
      const [s, c] = await Promise.all([adminApi.specParameters(cat), adminApi.certificateTypes(cat)]);
      setSpecs(s);
      setCerts(c);
    } catch (e) {
      setError(errorMessage(e, "Couldn’t load the template."));
    }
  }, []);

  useEffect(() => {
    setSpecs(null);
    setCerts(null);
    void load(category);
  }, [category, load]);

  const change = async (key: string, call: () => Promise<unknown>, done: string) => {
    setBusy(key);
    try {
      await call();
      await load(category);
      toast(done, "verified");
    } catch (e) {
      toast(errorMessage(e, "That change didn’t save."));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <LaneHeader
        eyebrow="Listing templates"
        title="What each category asks for"
        subtitle="Sellers fill these specification rows and upload these documents. A required row blocks submission until it is filled."
        actions={
          <Select
            aria-label="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={PRODUCT_CATEGORIES}
            className="w-44"
          />
        }
      />

      {error ? (
        <Notice tone="frozen" title="Couldn’t load" className="mt-8">
          {error}
        </Notice>
      ) : null}

      <div className="mt-8 grid gap-6 xl:grid-cols-2 xl:items-start">
        <section aria-label="Specifications" className="relief rounded-[30px] p-5 sm:p-7">
          <h2 className="t-label text-fg-3">Specifications · {category}</h2>
          {!specs ? (
            <Skeleton className="mt-4 h-32 w-full rounded-[18px]" />
          ) : specs.length === 0 ? (
            <p className="t-sub mt-4 text-fg-3">No specification rows yet for {category}.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {specs.map((p) => (
                <Row
                  key={p.id}
                  title={p.name}
                  sub={`${p.code} · ${p.valueType === "number" ? p.unit ?? "number" : "text"} · ${p.defaultOperator.toLowerCase()} by default`}
                  required={p.isRequired}
                  active={p.active}
                  disabled={!canManage || busy === p.id}
                  onRequired={(v) => change(p.id, () => adminApi.updateSpecParameter(p.id, { isRequired: v }), v ? "Now required" : "Now optional")}
                  onActive={(v) => change(p.id, () => adminApi.updateSpecParameter(p.id, { active: v }), v ? "Restored" : "Retired")}
                />
              ))}
            </ul>
          )}
          {canManage ? (
            <AddSpec
              busy={busy === "new-spec"}
              onAdd={(v) =>
                change(
                  "new-spec",
                  () => adminApi.createSpecParameter({ category, code: codeOf(v.name), name: v.name, valueType: v.unit === "text" ? "text" : "number", unit: v.unit === "text" ? null : v.unit || null, defaultOperator: v.operator as SpecParameter["defaultOperator"], isRequired: v.required }),
                  "Specification added",
                )
              }
            />
          ) : null}
        </section>

        <section aria-label="Documents" className="relief rounded-[30px] p-5 sm:p-7">
          <h2 className="t-label text-fg-3">Documents · {category}</h2>
          {!certs ? (
            <Skeleton className="mt-4 h-32 w-full rounded-[18px]" />
          ) : (
            <ul className="mt-4 space-y-2">
              {certs.map((t) => (
                <Row
                  key={t.id}
                  title={t.name}
                  sub={`${t.code} · ${t.category === "*" ? "every category" : t.category}`}
                  required={t.isRequired}
                  active={t.active}
                  disabled={!canManage || busy === t.id}
                  onRequired={(v) => change(t.id, () => adminApi.updateCertificateType(t.id, { isRequired: v }), v ? "Now required" : "Now optional")}
                  onActive={(v) => change(t.id, () => adminApi.updateCertificateType(t.id, { active: v }), v ? "Restored" : "Retired")}
                />
              ))}
            </ul>
          )}
          {canManage ? (
            <AddDocument
              category={category}
              busy={busy === "new-cert"}
              onAdd={(v) =>
                change(
                  "new-cert",
                  () => adminApi.createCertificateType({ category: v.everyCategory ? "*" : category, code: codeOf(v.name), name: v.name, isRequired: v.required }),
                  "Document type added",
                )
              }
            />
          ) : null}
          <p className="t-sub mt-4 text-fg-3">
            Making a document required for “every category” blocks every new submission that lacks it.
          </p>
        </section>
      </div>
    </div>
  );
}

function Row({
  title,
  sub,
  required,
  active,
  disabled,
  onRequired,
  onActive,
}: {
  title: string;
  sub: string;
  required: boolean;
  active: boolean;
  disabled: boolean;
  onRequired: (v: boolean) => void;
  onActive: (v: boolean) => void;
}) {
  return (
    <li className={cn("relief-sm flex flex-wrap items-center gap-3 rounded-[16px] px-4 py-3", !active && "opacity-60")}>
      <div className="min-w-0 flex-1">
        <p className="t-body flex flex-wrap items-center gap-2 text-fg">
          {title}
          {!active ? (
            <Chip tone="quiet" size="sm" noIcon>
              Retired
            </Chip>
          ) : required ? (
            <Chip tone="move" size="sm" noIcon>
              Required
            </Chip>
          ) : null}
        </p>
        <p className="t-code mt-0.5 truncate text-[12px] text-fg-3">{sub}</p>
      </div>
      {active ? (
        <Button size="sm" variant="quiet" disabled={disabled} onClick={() => onRequired(!required)}>
          {required ? "Make optional" : "Make required"}
        </Button>
      ) : null}
      <Button size="sm" variant="quiet" disabled={disabled} onClick={() => onActive(!active)}>
        {active ? "Retire" : "Restore"}
      </Button>
    </li>
  );
}

function AddSpec({
  busy,
  onAdd,
}: {
  busy: boolean;
  onAdd: (v: { name: string; unit: string; operator: string; required: boolean }) => void;
}) {
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("%");
  const [operator, setOperator] = useState("MAX");
  const [required, setRequired] = useState(false);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) return;
    onAdd({ name: name.trim(), unit: unit.trim(), operator, required });
    setName("");
  };
  return (
    <form onSubmit={submit} className="mt-6 grid gap-4 border-t border-line pt-6 sm:grid-cols-2">
      <Input label="New specification" placeholder="e.g. Admixture" maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className="sm:col-span-2" />
      <Input label="Unit" placeholder="%, mm, ppm — or “text”" maxLength={20} value={unit} onChange={(e) => setUnit(e.target.value)} hint="Type “text” for a written value." />
      <Select label="Stated as" value={operator} onChange={(e) => setOperator(e.target.value)} options={OPERATORS} />
      <Checkbox checked={required} onChange={setRequired} label="Required to submit a listing" className="sm:col-span-2" />
      <div className="sm:col-span-2">
        <Button type="submit" variant="secondary" loading={busy} disabled={name.trim().length < 2}>
          Add specification
        </Button>
      </div>
    </form>
  );
}

function AddDocument({
  category,
  busy,
  onAdd,
}: {
  category: string;
  busy: boolean;
  onAdd: (v: { name: string; everyCategory: boolean; required: boolean }) => void;
}) {
  const [name, setName] = useState("");
  const [everyCategory, setEveryCategory] = useState(false);
  const [required, setRequired] = useState(false);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) return;
    onAdd({ name: name.trim(), everyCategory, required });
    setName("");
  };
  return (
    <form onSubmit={submit} className="mt-6 grid gap-4 border-t border-line pt-6">
      <Input label="New document type" placeholder="e.g. Phytosanitary certificate" maxLength={150} value={name} onChange={(e) => setName(e.target.value)} />
      <Checkbox checked={everyCategory} onChange={setEveryCategory} label={`Ask for it in every category, not only ${category}`} />
      <Checkbox checked={required} onChange={setRequired} label="Required to submit a listing" />
      <div>
        <Button type="submit" variant="secondary" loading={busy} disabled={name.trim().length < 2}>
          Add document type
        </Button>
      </div>
    </form>
  );
}
