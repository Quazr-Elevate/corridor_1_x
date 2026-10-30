"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  adminApi,
  errorMessage,
  type AdminKybDocType,
  type AdminKybDocTypeIn,
  type KybInputKind,
} from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { COUNTRIES, countryName } from "@/components/account/countries";
import { LaneHeader } from "@/components/admin/tower";
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
  const [rows, setRows] = useState<AdminKybDocType[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [country, setCountry] = useState("IN");
  const [editing, setEditing] = useState<AdminKybDocType | "new" | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      setRows(await adminApi.kybTypes());
    } catch (e) {
      setErr(errorMessage(e, "Couldn't load document types."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const countries = useMemo(() => {
    const codes = new Set(["IN", "AE", ...(rows ?? []).map((r) => r.country)]);
    return [...codes];
  }, [rows]);
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
        subtitle="What businesses add under Business verification, per country. Required documents must be present before a business can send its profile for review."
        actions={
          <Button icon="plus" onClick={() => setEditing("new")}>
            New document type
          </Button>
        }
      />

      <div className="mt-6">
        <Segmented<string>
          label="Country"
          value={country}
          onChange={setCountry}
          options={countries.map((c) => ({
            value: c,
            label: countryName(c),
            count: (rows ?? []).filter((r) => r.country === c && r.active).length,
          }))}
        />
      </div>

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
            </div>
          ))
        )}
      </div>

      <p className="t-sub mt-6 flex items-center gap-1.5 text-fg-3">
        <Icon name="lock" size={13} /> Aadhaar can’t be added as a document type. Numbers businesses enter are stored encrypted.
      </p>

      <TypeSheet
        key={editing === "new" ? "new" : editing?.id ?? "none"}
        open={editing !== null}
        row={editing === "new" ? null : editing}
        country={country}
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
  onClose,
  onSaved,
}: {
  open: boolean;
  row: AdminKybDocType | null;
  country: string;
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
              options={COUNTRIES.map((c) => ({ value: c.code, label: `${c.flag} ${c.name}` }))}
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
