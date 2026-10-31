"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  adminApi,
  errorMessage,
  type AdminCountry,
  type AdminKybDocType,
  type AdminKybDocTypeIn,
  type KybInputKind,
} from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { COUNTRIES, countryName } from "@/components/account/countries";
import { LaneHeader } from "@/components/admin/tower";
import { useTower } from "@/components/shell/TowerShell";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Checkbox, Segmented } from "@/components/ui/Controls";
import { Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

const KIND_LABEL: Record<KybInputKind, string> = {
  value: "Number",
  file: "File",
  value_or_file: "Number or file",
  value_and_file: "Number and file",
};

const KIND_OPTIONS = (Object.keys(KIND_LABEL) as KybInputKind[]).map((k) => ({ value: k, label: KIND_LABEL[k] }));

/**
 * Document types — the per-country KYB list businesses pick from on their
 * profile. Ops decides which documents each country offers and which are
 * required before a business can send its profile for review. Types are
 * hidden, never deleted (existing entries keep their label). Every change is
 * written to the audit log.
 */
export default function KybTypesPage() {
  const toast = useToast();
  // Reviewers see the list; only super admins add or change it.
  const manage = useTower().can("catalog.manage");
  const [rows, setRows] = useState<AdminKybDocType[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [country, setCountry] = useState("IN");
  const [editing, setEditing] = useState<AdminKybDocType | "new" | null>(null);
  const [addingCountry, setAddingCountry] = useState(false);
  const [editingCountry, setEditingCountry] = useState<AdminCountry | null>(null);
  const [countryRows, setCountryRows] = useState<AdminCountry[] | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [types, cs] = await Promise.all([adminApi.kybTypes(), adminApi.kybCountries()]);
      setRows(types);
      setCountryRows(cs);
    } catch (e) {
      setErr(errorMessage(e, "Couldn't load document types."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Set-up countries: those with document types (the countries table also
  // holds placeholders seeded from old data, shown once they get documents).
  const countries = useMemo(() => {
    const withDocs = new Set((rows ?? []).map((r) => r.country));
    return (countryRows ?? []).filter((c) => withDocs.has(c.code)).map((c) => c.code);
  }, [rows, countryRows]);
  const current = (countryRows ?? []).find((c) => c.code === country) ?? null;
  const nameOf = (code: string) => (countryRows ?? []).find((c) => c.code === code)?.name ?? countryName(code);

  async function setCountryActive(c: AdminCountry, active: boolean) {
    try {
      const next = await adminApi.updateKybCountry(c.code, { active });
      setCountryRows((xs) => (xs ?? []).map((x) => (x.code === next.code ? next : x)));
      toast(active ? `${next.name} reopened for new businesses` : `${next.name} paused for new businesses`, active ? "verified" : "default");
    } catch (e) {
      toast(errorMessage(e, "Update failed."), "frozen");
    }
  }
  const list = (rows ?? []).filter((r) => r.country === country);

  async function toggle(row: AdminKybDocType, patch: Partial<AdminKybDocType>) {
    try {
      const next = await adminApi.updateKybType(row.id, patch);
      setRows((xs) => (xs ?? []).map((x) => (x.id === next.id ? next : x)));
      toast(`${next.name} updated`, "verified");
    } catch (e) {
      toast(errorMessage(e, "Update failed."), "frozen");
    }
  }

  return (
    <div className="pt-4">
      <LaneHeader
        eyebrow="Settings · KYB"
        title="Document types"
        subtitle="Businesses can only choose a country set up here. Each country has at least one required document — they must be present before a business can send its profile for review."
        actions={
          manage ? (
          <>
            <Button variant="secondary" icon="plus" onClick={() => setEditing("new")} disabled={!countries.length}>
              Add document
            </Button>
            <Button icon="globe" onClick={() => setAddingCountry(true)}>
              Add country
            </Button>
          </>
          ) : null
        }
      />

      <div className="mt-6">
        <Segmented<string>
          label="Country"
          value={country}
          onChange={setCountry}
          options={countries.map((c) => ({
            value: c,
            label: nameOf(c),
            count: (rows ?? []).filter((r) => r.country === c && r.active).length,
          }))}
        />
      </div>

      {current ? (
        <div className="relief mt-4 flex flex-wrap items-center justify-between gap-4 rounded-[22px] px-5 py-4">
          <div className="min-w-0">
            <p className="t-headline flex flex-wrap items-center gap-2 text-fg">
              <span aria-hidden="true">{current.flag}</span>
              {current.name}
              {current.active ? (
                <Chip tone="verified" size="sm" noIcon>Open for onboarding</Chip>
              ) : (
                <Chip tone="move" size="sm" noIcon>Paused</Chip>
              )}
            </p>
            <p className="t-sub mt-1 text-fg-3">
              <span className="t-code text-[11.5px]">{current.code}</span>
              {current.dialCode ? ` · ${current.dialCode}` : ""} · {current.defaultCurrency} · {current.regionLabel} /{" "}
              {current.postalLabel} · {current.requiredDocuments} required of {current.documents} ·{" "}
              {current.businesses} business{current.businesses === 1 ? "" : "es"}
            </p>
          </div>
          {manage ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="quiet" onClick={() => void setCountryActive(current, !current.active)}>
              {current.active ? "Pause onboarding" : "Reopen onboarding"}
            </Button>
            <Button size="sm" variant="secondary" icon="pen" onClick={() => setEditingCountry(current)}>
              Edit country
            </Button>
          </div>
          ) : null}
        </div>
      ) : null}

      {err ? (
        <div className="mt-6">
          <Notice tone="frozen" action={<Button size="sm" variant="secondary" onClick={() => void load()}>Try again</Button>}>
            {err}
          </Notice>
        </div>
      ) : null}

      <div className="mt-6 space-y-2.5">
        {rows === null && !err ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[76px] rounded-[22px]" />)
        ) : list.length === 0 ? (
          <Card className="p-2">
            <EmptyState icon="doc-check" title={`No documents for ${countryName(country)}`}>
              Businesses in this country can still add certificates with “Other”.
            </EmptyState>
          </Card>
        ) : (
          list.map((r) => (
            <div
              key={r.id}
              className={cn(
                "relief flex flex-wrap items-center justify-between gap-4 rounded-[22px] px-5 py-4",
                !r.active && "opacity-60",
              )}
            >
              <div className="min-w-0">
                <p className="t-headline flex flex-wrap items-center gap-2 text-fg">
                  {r.name}
                  {r.isMandatory ? <Chip tone="move" size="sm" noIcon>Required</Chip> : <Chip tone="quiet" size="sm" noIcon>Optional</Chip>}
                  {!r.active ? <Chip tone="neutral" size="sm" noIcon>Hidden</Chip> : null}
                </p>
                <p className="t-sub mt-1 text-fg-3">
                  <span className="t-code text-[11.5px]">{r.code}</span> · {KIND_LABEL[r.inputKind]}
                  {r.valuePattern ? " · format checked" : ""}
                  {r.isUnique ? " · one business per number" : ""}
                  {r.helpText ? ` · ${r.helpText}` : ""}
                </p>
              </div>
              {manage ? (
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="quiet" onClick={() => void toggle(r, { isMandatory: !r.isMandatory })}>
                  {r.isMandatory ? "Make optional" : "Make required"}
                </Button>
                <Button size="sm" variant="quiet" onClick={() => void toggle(r, { active: !r.active })}>
                  {r.active ? "Hide" : "Show"}
                </Button>
                <Button size="sm" variant="secondary" icon="pen" onClick={() => setEditing(r)}>
                  Edit
                </Button>
              </div>
              ) : null}
            </div>
          ))
        )}
      </div>

      <p className="t-sub mt-6 flex items-center gap-1.5 text-fg-3">
        <Icon name="lock" size={13} /> Aadhaar can’t be added as a document type. Numbers businesses enter are stored encrypted.
      </p>

      <CountrySheet
        open={addingCountry}
        existing={countries}
        onClose={() => setAddingCountry(false)}
        onSaved={(created) => {
          setRows((xs) => [...(xs ?? []), ...created]);
          setCountry(created[0].country);
          setAddingCountry(false);
          void adminApi.kybCountries().then(setCountryRows).catch(() => undefined);
          toast(`${countryName(created[0].country)} added with ${created.length} document${created.length === 1 ? "" : "s"}`, "verified");
        }}
      />

      <CountryEditSheet
        key={editingCountry?.code ?? "none"}
        country={editingCountry}
        onClose={() => setEditingCountry(null)}
        onSaved={(next) => {
          setCountryRows((xs) => (xs ?? []).map((x) => (x.code === next.code ? next : x)));
          setEditingCountry(null);
          toast(`${next.name} saved`, "verified");
        }}
      />

      <TypeSheet
        key={editing === "new" ? "new" : editing?.id ?? "none"}
        open={editing !== null}
        row={editing === "new" ? null : editing}
        country={country}
        countries={countries}
        countryName={nameOf}
        onClose={() => setEditing(null)}
        onSaved={(t) => {
          setRows((xs) => {
            const others = (xs ?? []).filter((x) => x.id !== t.id);
            return [...others, t].sort((a, b) => a.country.localeCompare(b.country) || a.sortOrder - b.sortOrder);
          });
          setCountry(t.country);
          setEditing(null);
          toast(`${t.name} saved`, "verified");
        }}
      />
    </div>
  );
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/^([0-9])/, "d_$1")
    .slice(0, 40);
}

function TypeSheet({
  open,
  row,
  country,
  countries,
  countryName: nameOf,
  onClose,
  onSaved,
}: {
  open: boolean;
  row: AdminKybDocType | null;
  country: string;
  countries: string[];
  countryName: (code: string) => string;
  onClose: () => void;
  onSaved: (t: AdminKybDocType) => void;
}) {
  const [v, setV] = useState<AdminKybDocTypeIn>(() =>
    row
      ? { ...row, valuePattern: row.valuePattern ?? "", valuePlaceholder: row.valuePlaceholder ?? "", helpText: row.helpText ?? "" }
      : { country, code: "", name: "", inputKind: "value", valuePattern: "", valuePlaceholder: "", helpText: "", isMandatory: false, isUnique: true, sortOrder: 100, active: true },
  );
  const [codeTouched, setCodeTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof AdminKybDocTypeIn>(k: K, value: AdminKybDocTypeIn[K]) => setV((x) => ({ ...x, [k]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (v.name.trim().length < 2) return setError("Enter a name.");
    if (/aadh?aa?r/i.test(`${v.name} ${v.code}`)) return setError("Aadhaar can’t be a KYB document.");
    if (v.valuePattern) {
      try {
        new RegExp(v.valuePattern);
      } catch {
        return setError("The format pattern isn’t a valid regular expression.");
      }
    }
    setSaving(true);
    try {
      const common = {
        name: v.name.trim(),
        inputKind: v.inputKind,
        valuePattern: v.valuePattern?.trim() || null,
        valuePlaceholder: v.valuePlaceholder?.trim() || null,
        helpText: v.helpText?.trim() || null,
        isMandatory: v.isMandatory,
        isUnique: v.isUnique,
        sortOrder: Number(v.sortOrder) || 0,
        active: v.active,
      };
      onSaved(
        row
          ? await adminApi.updateKybType(row.id, common)
          : await adminApi.createKybType({ ...common, country: v.country, code: v.code.trim() || slugify(v.name) }),
      );
    } catch (err) {
      setError(errorMessage(err, "Save failed."));
    } finally {
      setSaving(false);
    }
  }

  const needsValue = v.inputKind !== "file";

  return (
    <Sheet
      open={open}
      onClose={onClose}
      size="md"
      title={row ? `Edit ${row.name}` : "New document type"}
      description={row ? `${countryName(row.country)} · ${row.code}` : "Businesses in this country will see it under Business verification."}
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        {!row ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Select
              label="Country"
              value={v.country}
              onChange={(e) => set("country", e.target.value)}
              options={countries.map((c) => ({ value: c, label: nameOf(c) }))}
              hint="New countries: use Add country."
            />
            <Input
              label="Code"
              hint="Fixed once saved."
              value={codeTouched ? v.code : v.code || slugify(v.name)}
              onChange={(e) => {
                setCodeTouched(true);
                set("code", e.target.value.toLowerCase());
              }}
              inputClassName="t-code"
            />
          </div>
        ) : null}
        <Input
          label="Name"
          placeholder="e.g. Spices Board registration"
          value={v.name}
          onChange={(e) => {
            set("name", e.target.value);
            if (!codeTouched && !row) set("code", slugify(e.target.value));
          }}
          maxLength={150}
        />
        <Select
          label="Businesses provide"
          value={v.inputKind}
          onChange={(e) => set("inputKind", e.target.value as KybInputKind)}
          options={KIND_OPTIONS}
        />
        {needsValue ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Format pattern"
              optional
              hint="Regular expression the number must match."
              value={v.valuePattern ?? ""}
              onChange={(e) => set("valuePattern", e.target.value)}
              inputClassName="t-code"
            />
            <Input
              label="Example"
              optional
              value={v.valuePlaceholder ?? ""}
              onChange={(e) => set("valuePlaceholder", e.target.value)}
              inputClassName="t-code"
              maxLength={60}
            />
          </div>
        ) : null}
        <Input
          label="Help text"
          optional
          placeholder="e.g. Needed to export outside India"
          value={v.helpText ?? ""}
          onChange={(e) => set("helpText", e.target.value)}
          maxLength={300}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Checkbox checked={Boolean(v.isMandatory)} onChange={(x) => set("isMandatory", x)} label="Required for verification" />
          <Checkbox checked={Boolean(v.isUnique)} onChange={(x) => set("isUnique", x)} label="One business per number" />
          <Checkbox checked={Boolean(v.active)} onChange={(x) => set("active", x)} label="Shown to businesses" />
          <Input
            label="Order"
            type="number"
            min={0}
            max={9999}
            value={String(v.sortOrder ?? 0)}
            onChange={(e) => set("sortOrder", Number(e.target.value))}
          />
        </div>
        {error ? <Notice tone="frozen">{error}</Notice> : null}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            {row ? "Save changes" : "Create"}
          </Button>
        </div>
      </form>
    </Sheet>
  );
}

// ── Add country ──────────────────────────────────────────────────────

interface DraftDoc {
  key: number;
  name: string;
  code: string;
  codeTouched: boolean;
  inputKind: KybInputKind;
  valuePattern: string;
  valuePlaceholder: string;
  helpText: string;
  isMandatory: boolean;
}

let draftSeq = 0;
const blankDoc = (mandatory: boolean): DraftDoc => ({
  key: ++draftSeq,
  name: "",
  code: "",
  codeTouched: false,
  inputKind: "value_or_file",
  valuePattern: "",
  valuePlaceholder: "",
  helpText: "",
  isMandatory: mandatory,
});

/**
 * A country is added together with its documents — at least one required —
 * so no business can pick a country without knowing what to submit.
 */
function CountrySheet({
  open,
  existing,
  onClose,
  onSaved,
}: {
  open: boolean;
  existing: string[];
  onClose: () => void;
  onSaved: (rows: AdminKybDocType[]) => void;
}) {
  const options = COUNTRIES.filter((c) => !existing.includes(c.code));
  const [country, setCountry] = useState(options[0]?.code ?? "");
  const [other, setOther] = useState({ code: "", name: "", flag: "", dialCode: "", currency: "USD" as "INR" | "AED" | "USD" });
  const isOther = country === OTHER_COUNTRY;
  const [docs, setDocs] = useState<DraftDoc[]>(() => [blankDoc(true)]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setCountry(COUNTRIES.find((c) => !existing.includes(c.code))?.code ?? OTHER_COUNTRY);
      setOther({ code: "", name: "", flag: "", dialCode: "", currency: "USD" });
      setDocs([blankDoc(true)]);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const update = (key: number, patch: Partial<DraftDoc>) =>
    setDocs((xs) =>
      xs.map((d) => {
        if (d.key !== key) return d;
        const next = { ...d, ...patch };
        if (patch.name !== undefined && !d.codeTouched) next.code = slugify(patch.name);
        return next;
      }),
    );

  const required = docs.filter((d) => d.isMandatory).length;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!country) return setError("Pick a country.");
    const code = isOther ? other.code.trim().toUpperCase() : country;
    if (isOther && !/^[A-Z]{2}$/.test(code)) return setError("Enter the 2-letter ISO country code (e.g. KE).");
    if (isOther && other.name.trim().length < 2) return setError("Enter the country’s name.");
    if (docs.some((d) => d.name.trim().length < 2)) return setError("Every document needs a name.");
    if (!required) return setError("Mark at least one document as required.");
    if (docs.some((d) => /aadh?aa?r/i.test(d.name + d.code))) return setError("Aadhaar can’t be a KYB document.");
    const codes = docs.map((d) => d.code || slugify(d.name));
    if (new Set(codes).size !== codes.length) return setError("Two documents have the same code — rename one.");
    for (const d of docs) {
      if (d.valuePattern) {
        try {
          new RegExp(d.valuePattern);
        } catch {
          return setError(`The format pattern for “${d.name}” isn’t a valid regular expression.`);
        }
      }
    }
    setSaving(true);
    try {
      onSaved(
        await adminApi.createKybCountry(
          code,
          docs.map((d, i) => ({
            code: d.code || slugify(d.name),
            name: d.name.trim(),
            inputKind: d.inputKind,
            valuePattern: d.inputKind === "file" ? null : d.valuePattern.trim() || null,
            valuePlaceholder: d.inputKind === "file" ? null : d.valuePlaceholder.trim() || null,
            helpText: d.helpText.trim() || null,
            isMandatory: d.isMandatory,
            isUnique: true,
            sortOrder: (i + 1) * 10,
          })),
          isOther
            ? {
                name: other.name.trim(),
                flag: other.flag.trim() || null,
                dialCode: other.dialCode.trim() || null,
                defaultCurrency: other.currency,
              }
            : {},
        ),
      );
    } catch (err) {
      setError(errorMessage(err, "Couldn’t add the country."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      size="lg"
      title="Add a country"
      description="Enter the documents businesses from this country must provide. At least one is required."
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <Select
          label="Country"
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          options={[
            ...options.map((c) => ({ value: c.code, label: `${c.flag} ${c.name}` })),
            { value: OTHER_COUNTRY, label: "Other country…" },
          ]}
          hint={isOther ? undefined : "Name, dial code, currency and address labels are filled in for you — edit them later."}
        />
        {isOther ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label="ISO code"
              placeholder="KE"
              maxLength={2}
              value={other.code}
              onChange={(e) => setOther((o) => ({ ...o, code: e.target.value.toUpperCase() }))}
              inputClassName="t-code"
            />
            <Input label="Name" placeholder="Kenya" value={other.name} onChange={(e) => setOther((o) => ({ ...o, name: e.target.value }))} maxLength={100} />
            <Input label="Flag" optional placeholder="🇰🇪" value={other.flag} onChange={(e) => setOther((o) => ({ ...o, flag: e.target.value }))} maxLength={8} />
            <Input label="Dial code" optional placeholder="+254" value={other.dialCode} onChange={(e) => setOther((o) => ({ ...o, dialCode: e.target.value }))} maxLength={6} />
            <Select
              label="Default currency"
              value={other.currency}
              onChange={(e) => setOther((o) => ({ ...o, currency: e.target.value as "INR" | "AED" | "USD" }))}
              options={["USD", "INR", "AED"]}
            />
          </div>
        ) : null}

        <div className="space-y-3">
          {docs.map((d, i) => (
            <div key={d.key} className="well rounded-[20px] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="t-label text-fg-3">Document {i + 1}</p>
                {docs.length > 1 ? (
                  <button
                    type="button"
                    onClick={() => setDocs((xs) => xs.filter((x) => x.key !== d.key))}
                    className="t-sub text-fg-3 hover:text-fg"
                  >
                    Remove
                  </button>
                ) : null}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label="Name"
                  placeholder="e.g. Commercial registration"
                  value={d.name}
                  onChange={(e) => update(d.key, { name: e.target.value })}
                  maxLength={150}
                />
                <Select
                  label="Businesses provide"
                  value={d.inputKind}
                  onChange={(e) => update(d.key, { inputKind: e.target.value as KybInputKind })}
                  options={KIND_OPTIONS}
                />
                {d.inputKind !== "file" ? (
                  <>
                    <Input
                      label="Format pattern"
                      optional
                      value={d.valuePattern}
                      onChange={(e) => update(d.key, { valuePattern: e.target.value })}
                      inputClassName="t-code"
                    />
                    <Input
                      label="Example"
                      optional
                      value={d.valuePlaceholder}
                      onChange={(e) => update(d.key, { valuePlaceholder: e.target.value })}
                      inputClassName="t-code"
                      maxLength={60}
                    />
                  </>
                ) : null}
                <Input
                  label="Help text"
                  optional
                  value={d.helpText}
                  onChange={(e) => update(d.key, { helpText: e.target.value })}
                  maxLength={300}
                />
                <div className="flex items-end pb-3">
                  <Checkbox
                    checked={d.isMandatory}
                    onChange={(x) => update(d.key, { isMandatory: x })}
                    label="Required for verification"
                  />
                </div>
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setDocs((xs) => [...xs, blankDoc(false)])}
            className="flex w-full items-center justify-center gap-2 rounded-[20px] border border-dashed border-line-2 py-3 text-[14px] font-medium text-fg-2 hover:text-fg"
          >
            <Icon name="plus" size={15} /> Add another document
          </button>
        </div>

        <p className={cn("t-sub", required ? "text-fg-3" : "text-danger")}>
          {required
            ? `${required} required, ${docs.length - required} optional.`
            : "Mark at least one document as required."}
        </p>
        {error ? <Notice tone="frozen">{error}</Notice> : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving} disabled={!required}>
            Add country
          </Button>
        </div>
      </form>
    </Sheet>
  );
}

const OTHER_COUNTRY = "__other__";

/** Edit a country's details (code is fixed); pausing is on the country header. */
function CountryEditSheet({
  country,
  onClose,
  onSaved,
}: {
  country: AdminCountry | null;
  onClose: () => void;
  onSaved: (c: AdminCountry) => void;
}) {
  const [v, setV] = useState(() => ({
    name: country?.name ?? "",
    flag: country?.flag ?? "",
    dialCode: country?.dialCode ?? "",
    defaultCurrency: (country?.defaultCurrency ?? "USD") as "INR" | "AED" | "USD",
    regionLabel: country?.regionLabel ?? "",
    postalLabel: country?.postalLabel ?? "",
    postalPattern: country?.postalPattern ?? "",
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v) => (value: string) => setV((x) => ({ ...x, [k]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!country) return;
    setError(null);
    if (v.name.trim().length < 2) return setError("Enter the country’s name.");
    if (v.postalPattern) {
      try {
        new RegExp(v.postalPattern);
      } catch {
        return setError("The postcode pattern isn’t a valid regular expression.");
      }
    }
    setSaving(true);
    try {
      onSaved(
        await adminApi.updateKybCountry(country.code, {
          name: v.name.trim(),
          flag: v.flag.trim() || null,
          dialCode: v.dialCode.trim() || null,
          defaultCurrency: v.defaultCurrency,
          regionLabel: v.regionLabel.trim() || "State / region",
          postalLabel: v.postalLabel.trim() || "Postal code",
          postalPattern: v.postalPattern.trim() || null,
        }),
      );
    } catch (err) {
      setError(errorMessage(err, "Save failed."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      open={country !== null}
      onClose={onClose}
      size="md"
      title={country ? `Edit ${country.name}` : "Edit country"}
      description={country ? `${country.code} · the code can’t change.` : undefined}
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Name" value={v.name} onChange={(e) => set("name")(e.target.value)} maxLength={100} />
          <Input label="Flag" optional value={v.flag} onChange={(e) => set("flag")(e.target.value)} maxLength={8} />
          <Input label="Dial code" optional placeholder="+91" value={v.dialCode} onChange={(e) => set("dialCode")(e.target.value)} maxLength={6} />
          <Select
            label="Default currency"
            hint="New users from this country see prices in it."
            value={v.defaultCurrency}
            onChange={(e) => set("defaultCurrency")(e.target.value)}
            options={["USD", "INR", "AED"]}
          />
          <Input label="Region label" placeholder="State" value={v.regionLabel} onChange={(e) => set("regionLabel")(e.target.value)} maxLength={30} />
          <Input label="Postcode label" placeholder="PIN code" value={v.postalLabel} onChange={(e) => set("postalLabel")(e.target.value)} maxLength={30} />
        </div>
        <Input
          label="Postcode format"
          optional
          hint="Regular expression, e.g. [1-9][0-9]{5}"
          value={v.postalPattern}
          onChange={(e) => set("postalPattern")(e.target.value)}
          inputClassName="t-code"
        />
        {error ? <Notice tone="frozen">{error}</Notice> : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Save country
          </Button>
        </div>
      </form>
    </Sheet>
  );
}
