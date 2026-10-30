"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  adminApi,
  errorMessage,
  type DocRequirement,
  type DocRequirementIn,
  type DocRequirementPatch,
} from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { Reveal } from "@/components/motion";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Checkbox } from "@/components/ui/Controls";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { COUNTRIES } from "@/components/account/countries";
import { LaneHeader } from "@/components/admin/tower";

/**
 * Doc rules — admin-managed catalog of which documents each country
 * requires during KYB. Rows seeded here surface as upload slots on
 * every business profile for that country.
 *
 * Country + slug are immutable once a row exists (changing them would
 * orphan the uploads that fill the slot). Everything else is editable;
 * ``deactivate`` is a soft-delete.
 */

const COUNTRY_OPTIONS = COUNTRIES.map((c) => ({ value: c.code, label: `${c.name} (${c.code})` }));

const SLUG_HINT = "Lower-case machine key — e.g. gstin, iec, trade_license.";
const SLUG_RE = /^[a-z0-9][a-z0-9_-]{0,39}$/;

const slugError = (v: string): string | null => {
  if (!v) return "Pick a slug.";
  if (!SLUG_RE.test(v)) return "Lowercase, up to 40 chars; letters/digits/underscore/hyphen.";
  return null;
};

const nameOf = (code: string) => COUNTRIES.find((c) => c.code === code)?.name ?? code;

export default function DocRequirementsPage() {
  const toast = useToast();
  const [rows, setRows] = useState<DocRequirement[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await adminApi.listDocRequirements({ includeInactive: showInactive });
      setRows(r);
      setErr(null);
    } catch (e) {
      setErr(errorMessage(e, "Couldn’t load the catalog."));
      setRows([]);
    }
  }, [showInactive]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    if (!rows || !selectedCountry) return [];
    return rows.filter((r) => r.countryCode === selectedCountry);
  }, [rows, selectedCountry]);

  return (
    <div className="pt-4">
      <LaneHeader
        eyebrow="Lane · Doc rules"
        title="Country document requirements"
        subtitle="Seed the catalog of mandatory KYB documents per country. Changes take effect for draft and rejected businesses immediately; verified ones are grandfathered."
      />

      <Reveal className="mt-10">
        <AddRow onCreated={load} toastSuccess={(m) => toast(m, "verified")} />
      </Reveal>

      <Reveal delay={0.08} className="mt-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="t-title3 text-fg">Catalog</h2>
            <p className="t-sub mt-1 text-fg-3">
              Choose a country to review or edit its requirements.
            </p>
          </div>
          <label className="t-sub inline-flex items-center gap-2 text-fg-2">
            <Checkbox
              checked={showInactive}
              onChange={setShowInactive}
              label={<span className="text-fg-2">Show deactivated</span>}
            />
          </label>
        </div>

        <div className="mt-5 max-w-md">
          <Select
            night
            label="Country"
            placeholder="Choose a country"
            value={selectedCountry}
            options={COUNTRY_OPTIONS}
            onChange={(e) => setSelectedCountry(e.target.value)}
          />
        </div>

        <div className="mt-6 space-y-5">
          {err ? <Notice tone="frozen">{err}</Notice> : null}

          {rows === null ? (
            <div className="space-y-3" aria-busy="true">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : !selectedCountry ? (
            <div className="relief rounded-[22px] p-10 text-center">
              <p className="t-title3 text-fg">Pick a country above</p>
              <p className="t-sub mt-2 text-fg-3">
                Its requirements will show up here.
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="relief rounded-[22px] p-10 text-center">
              <p className="t-title3 text-fg">
                No requirements for {nameOf(selectedCountry)} yet
              </p>
              <p className="t-sub mt-2 text-fg-3">
                Use "Add row" above to seed the first one.
              </p>
            </div>
          ) : (
            <section
              aria-label={`${nameOf(selectedCountry)} requirements`}
              className="relief rounded-[22px] p-5"
            >
              <header className="flex items-center justify-between gap-3 pb-3">
                <div>
                  <p className="t-label text-fg-3">{selectedCountry}</p>
                  <h3 className="t-headline text-fg">{nameOf(selectedCountry)}</h3>
                </div>
                <span className="t-code text-fg-3">{filtered.length}</span>
              </header>
              <ul className="divide-y divide-fg/[0.08]">
                {filtered.map((r) => (
                  <RowItem key={r.id} row={r} onPatched={load} toast={toast} />
                ))}
              </ul>
            </section>
          )}
        </div>
      </Reveal>
    </div>
  );
}

/* ─────────────────────────────── Add form ────────────────────────── */

function AddRow({
  onCreated,
  toastSuccess,
}: {
  onCreated: () => void;
  toastSuccess: (m: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [countryCode, setCountryCode] = useState("");
  const [slug, setSlug] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [helpUrl, setHelpUrl] = useState("");
  const [isMandatory, setIsMandatory] = useState(true);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const reset = () => {
    setCountryCode("");
    setSlug("");
    setDisplayName("");
    setDescription("");
    setHelpUrl("");
    setIsMandatory(true);
    setErrors({});
    setFormError(null);
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const fe: typeof errors = {};
    if (!countryCode) fe.countryCode = "Pick a country.";
    const se = slugError(slug);
    if (se) fe.slug = se;
    if (!displayName.trim() || displayName.trim().length < 2) fe.displayName = "At least 2 characters.";
    if (helpUrl && !/^https?:\/\//i.test(helpUrl.trim())) fe.helpUrl = "Must start with http:// or https://.";
    setErrors(fe);
    if (Object.keys(fe).length) return;

    setBusy(true);
    setFormError(null);
    const payload: DocRequirementIn = {
      countryCode,
      slug: slug.trim(),
      displayName: displayName.trim(),
      description: description.trim() || null,
      helpUrl: helpUrl.trim() || null,
      isMandatory,
    };
    try {
      await adminApi.createDocRequirement(payload);
      toastSuccess(`Added ${payload.slug} for ${countryCode}.`);
      reset();
      setOpen(false);
      onCreated();
    } catch (e) {
      setFormError(errorMessage(e, "Couldn’t save."));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <div className="relief flex items-center justify-between gap-4 rounded-[22px] p-5">
        <div>
          <p className="t-title3 text-fg">Add a requirement</p>
          <p className="t-sub mt-1 text-fg-3">
            Pick a country, enter a slug (e.g. <span className="t-code">gstin</span>), and give it a display name.
          </p>
        </div>
        <Button variant="primary" icon="plus" onClick={() => setOpen(true)}>
          Add row
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="relief rounded-[22px] p-5 sm:p-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Select
          night
          label="Country"
          required
          placeholder="Choose a country"
          value={countryCode}
          options={COUNTRY_OPTIONS}
          error={errors.countryCode}
          onChange={(e) => {
            setCountryCode(e.target.value);
            setErrors((er) => ({ ...er, countryCode: undefined }));
          }}
        />
        <Input
          night
          label="Slug"
          required
          hint={SLUG_HINT}
          placeholder="gstin"
          value={slug}
          maxLength={40}
          error={errors.slug}
          onChange={(e) => {
            setSlug(e.target.value.toLowerCase());
            setErrors((er) => ({ ...er, slug: undefined }));
          }}
        />
        <Input
          night
          label="Display name"
          required
          placeholder="GSTIN certificate"
          value={displayName}
          maxLength={100}
          error={errors.displayName}
          onChange={(e) => {
            setDisplayName(e.target.value);
            setErrors((er) => ({ ...er, displayName: undefined }));
          }}
          className="sm:col-span-2"
        />
        <Textarea
          night
          label="Description"
          optional
          placeholder="PDF of your GST registration certificate."
          value={description}
          maxLength={500}
          onChange={(e) => setDescription(e.target.value)}
          className="sm:col-span-2"
          rows={2}
        />
        <Input
          night
          label="Help URL"
          optional
          placeholder="https://www.example.gov/how-to-find-your-gstin"
          value={helpUrl}
          maxLength={500}
          error={errors.helpUrl}
          onChange={(e) => {
            setHelpUrl(e.target.value);
            setErrors((er) => ({ ...er, helpUrl: undefined }));
          }}
          className="sm:col-span-2"
        />
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <Checkbox
          checked={isMandatory}
          onChange={setIsMandatory}
          label={<span className="text-fg-2">Mandatory to submit for verification</span>}
        />
        <div className="flex items-center gap-2">
          <Button
            variant="quiet"
            type="button"
            onClick={() => {
              reset();
              setOpen(false);
            }}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button variant="primary" type="submit" loading={busy}>
            Create requirement
          </Button>
        </div>
      </div>

      {formError ? <Notice tone="frozen" className="mt-4">{formError}</Notice> : null}
    </form>
  );
}

/* ─────────────────────────────── Row item ────────────────────────── */

function RowItem({
  row,
  onPatched,
  toast,
}: {
  row: DocRequirement;
  onPatched: () => void;
  toast: (msg: string, tone?: "verified" | "frozen" | "default") => void;
}) {
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(row.displayName);
  const [description, setDescription] = useState(row.description ?? "");
  const [helpUrl, setHelpUrl] = useState(row.helpUrl ?? "");
  const [isMandatory, setIsMandatory] = useState(row.isMandatory);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});

  const resetState = () => {
    setDisplayName(row.displayName);
    setDescription(row.description ?? "");
    setHelpUrl(row.helpUrl ?? "");
    setIsMandatory(row.isMandatory);
    setErrors({});
  };

  async function save() {
    const fe: typeof errors = {};
    if (!displayName.trim() || displayName.trim().length < 2) fe.displayName = "At least 2 characters.";
    if (helpUrl && !/^https?:\/\//i.test(helpUrl.trim())) fe.helpUrl = "Must start with http:// or https://.";
    setErrors(fe);
    if (Object.keys(fe).length) return;

    setBusy(true);
    const patch: DocRequirementPatch = {};
    if (displayName.trim() !== row.displayName) patch.displayName = displayName.trim();
    if ((description.trim() || null) !== row.description) patch.description = description.trim() || null;
    if ((helpUrl.trim() || null) !== row.helpUrl) patch.helpUrl = helpUrl.trim() || null;
    if (isMandatory !== row.isMandatory) patch.isMandatory = isMandatory;
    try {
      await adminApi.updateDocRequirement(row.id, patch);
      toast("Saved.", "verified");
      setEditing(false);
      onPatched();
    } catch (e) {
      toast(errorMessage(e, "Couldn’t save."), "frozen");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive() {
    if (busy) return;
    setBusy(true);
    try {
      await adminApi.updateDocRequirement(row.id, { isActive: !row.isActive });
      toast(row.isActive ? "Deactivated." : "Reactivated.", row.isActive ? "default" : "verified");
      onPatched();
    } catch (e) {
      toast(errorMessage(e, "Couldn’t update."), "frozen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="t-code text-fg-3">{row.slug}</span>
            {row.isMandatory ? (
              <Chip tone="verified">Mandatory</Chip>
            ) : (
              <Chip tone="move">Optional</Chip>
            )}
            {!row.isActive ? <Chip tone="frozen">Deactivated</Chip> : null}
          </div>
          {editing ? (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Input
                night
                label="Display name"
                value={displayName}
                maxLength={100}
                error={errors.displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="sm:col-span-2"
              />
              <Textarea
                night
                label="Description"
                value={description}
                maxLength={500}
                onChange={(e) => setDescription(e.target.value)}
                className="sm:col-span-2"
                rows={2}
              />
              <Input
                night
                label="Help URL"
                value={helpUrl}
                maxLength={500}
                error={errors.helpUrl}
                onChange={(e) => setHelpUrl(e.target.value)}
                className="sm:col-span-2"
              />
              <Checkbox
                checked={isMandatory}
                onChange={setIsMandatory}
                label={<span className="text-fg-2">Mandatory to submit</span>}
              />
            </div>
          ) : (
            <div className="mt-1">
              <p className="t-callout text-fg">{row.displayName}</p>
              {row.description ? <p className="t-sub mt-1 text-fg-3">{row.description}</p> : null}
              {row.helpUrl ? (
                <a
                  href={/^https?:\/\//i.test(row.helpUrl) ? row.helpUrl : `https://${row.helpUrl}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="t-sub mt-1 inline-flex items-center gap-1 text-fg-2 underline decoration-fg/30 underline-offset-4 hover:text-fg"
                >
                  <Icon name="arrow-up-right" size={14} /> How to find this
                </a>
              ) : null}
            </div>
          )}
          <p className="t-code mt-2 text-fg-3">
            Updated by {row.updatedBy} · {new Date(row.updatedAt).toLocaleString()}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          {editing ? (
            <>
              <Button variant="primary" size="sm" onClick={save} loading={busy}>
                Save
              </Button>
              <Button
                variant="quiet"
                size="sm"
                onClick={() => {
                  resetState();
                  setEditing(false);
                }}
                disabled={busy}
              >
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button variant="secondary" size="sm" onClick={() => setEditing(true)} disabled={busy}>
                Edit
              </Button>
              <Button variant="quiet" size="sm" onClick={toggleActive} disabled={busy}>
                {row.isActive ? "Deactivate" : "Reactivate"}
              </Button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}
