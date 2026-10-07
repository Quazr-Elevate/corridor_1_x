"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Check,
  Download,
  FileText,
  Image as ImageIcon,
  Loader2,
  Pencil,
  ShieldCheck,
  Shield,
  Undo2,
  X,
} from "lucide-react";
import {
  adminApi,
  type UserDetail,
  type UserPatch,
  type VerifyDoc,
} from "@/lib/adminApi";
import { RejectReasonModal } from "@/components/admin/RejectReasonModal";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

// Field layout drives the admin user detail page. The user asked that
// the Verified-badge mandatory fields appear first (so the admin can
// decide on approve/reject at a glance), with everything else grouped
// below as a secondary section.
//
// ``source`` tells FieldGrid which draft bucket (profile vs business)
// to write back into on edit, so the single top-of-page layout can mix
// fields from both tables.

type FieldSource = "profile" | "business";

interface AdminField {
  key: string;
  label: string;
  source: FieldSource;
  type?: "text" | "textarea";
  cols?: 1 | 2;
}

// Keys the backend treats as mandatory for the Verified badge. Mirrors
// backend/app/verification.py — update both in lockstep.
const MANDATORY_KEYS = new Set<string>([
  "fullName",
  "position",
  "phone",
  "legalName",
  "industry",
  "operatingCountries",
  "tradePosition",
]);

const MANDATORY_FIELDS_LIST: AdminField[] = [
  { key: "fullName",           label: "Full name",           source: "profile" },
  { key: "position",           label: "Position",            source: "profile" },
  { key: "phone",              label: "Phone",               source: "profile" },
  { key: "legalName",          label: "Legal company name",  source: "business" },
  { key: "industry",           label: "Industry",            source: "business" },
  { key: "operatingCountries", label: "Operating countries", source: "business" },
  { key: "tradePosition",      label: "Trade position",      source: "business" },
];

// Everything the user *can* edit on My Account but is not required for
// the badge. We skipped these before (website, department, seller
// polish fields, long-form intro) because they're nice-to-haves, not
// hygiene checks.
const OPTIONAL_FIELDS_LIST: AdminField[] = [
  { key: "department",         label: "Department",          source: "profile" },
  { key: "websiteUrl",         label: "Website",             source: "business" },
  { key: "sellerType",         label: "Seller type",         source: "business" },
  { key: "exportStatus",       label: "Export status",       source: "business" },
  { key: "targetMarkets",      label: "Target markets",      source: "business" },
  { key: "mainObjective",      label: "Main objective",      source: "business", cols: 2 },
  { key: "companyIntroduction",label: "Company introduction",source: "business", type: "textarea", cols: 2 },
];

// Union of every editable key — used by the PATCH builder below.
const ALL_PROFILE_KEYS = [...MANDATORY_FIELDS_LIST, ...OPTIONAL_FIELDS_LIST]
  .filter((f) => f.source === "profile")
  .map((f) => f.key);
const ALL_BUSINESS_KEYS = [...MANDATORY_FIELDS_LIST, ...OPTIONAL_FIELDS_LIST]
  .filter((f) => f.source === "business")
  .map((f) => f.key);

export default function AdminUserDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [user, setUser] = useState<UserDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState<"verify" | "reject" | null>(null);
  const [preview, setPreview] = useState<VerifyDoc | null>(null);
  const [rejectTarget, setRejectTarget] = useState<VerifyDoc | null>(null);

  // Local draft state for edit mode. We clone the server data into these on
  // "Edit", push whatever's set when Save is clicked. Hitting Cancel discards.
  // Two buckets instead of three (previously profile/company/biz) because
  // the backend only has two tables — the "Mandatory" vs "Optional"
  // grouping on screen is purely cosmetic.
  const [businessName, setBusinessName] = useState("");
  const [profileDraft, setProfileDraft] = useState<Record<string, unknown>>({});
  const [businessDraft, setBusinessDraft] = useState<Record<string, unknown>>({});
  const [rejectUser, setRejectUser] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const u = await adminApi.user(id);
      setUser(u);
      resetDraft(u);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) void load();
  }, [id, load]);

  function resetDraft(u: UserDetail) {
    setBusinessName(u.businessName ?? "");
    const prof: Record<string, unknown> = {};
    const biz: Record<string, unknown> = {};
    for (const k of ALL_PROFILE_KEYS) {
      prof[k] = (u.profile ?? {})[k] ?? "";
    }
    for (const k of ALL_BUSINESS_KEYS) {
      biz[k] = (u.businessProfile ?? {})[k] ?? "";
    }
    setProfileDraft(prof);
    setBusinessDraft(biz);
  }

  async function save() {
    if (!user) return;
    setSaving(true);
    setErr(null);
    try {
      const patch: UserPatch = {
        businessName: businessName.trim() || null,
        profile: cleanDraft(profileDraft, ALL_PROFILE_KEYS),
        businessProfile: cleanDraft(businessDraft, ALL_BUSINESS_KEYS),
      };
      const updated = await adminApi.patchUser(user.userId, patch);
      setUser(updated);
      resetDraft(updated);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function doVerify() {
    if (!user) return;
    setBusyAction("verify");
    try {
      await adminApi.verifyUser(user.userId);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Verify failed");
    } finally {
      setBusyAction(null);
    }
  }

  async function doReject(reason: string) {
    if (!user) return;
    setBusyAction("reject");
    try {
      await adminApi.rejectUser(user.userId, reason);
      await load();
    } finally {
      setBusyAction(null);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto flex max-w-[1240px] justify-center px-6 py-16">
        <Loader2
          className="h-6 w-6 animate-spin"
          style={{ color: "var(--sp-lime)" }}
        />
      </div>
    );
  }
  if (err && !user) {
    return (
      <div className="mx-auto max-w-[1240px] px-6 py-8">
        <p className="text-[13px]" style={{ color: "var(--sp-error)" }}>
          {err}
        </p>
      </div>
    );
  }
  if (!user) return null;

  const initials = (user.profile?.fullName as string | undefined)
    ?.split(/\s+/)
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="mx-auto max-w-[1240px] px-6 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="flex items-start gap-4">
          <Link
            href="/admin/users"
            className="sp-chip"
            style={{ paddingLeft: "0.75rem" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Users
          </Link>
        </div>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <button
                type="button"
                onClick={() => {
                  resetDraft(user);
                  setEditing(false);
                }}
                className="sp-chip"
              >
                <Undo2 className="h-3.5 w-3.5" aria-hidden /> Cancel
              </button>
              <button
                type="button"
                onClick={save}
                disabled={saving}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold transition disabled:opacity-50"
                style={{
                  background: "var(--sp-lime)",
                  color: "var(--sp-lime-fg)",
                }}
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <Check className="h-3.5 w-3.5" aria-hidden />
                )}
                Save changes
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setRejectUser(true)}
                disabled={!!busyAction || user.status === "rejected"}
                className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-semibold transition disabled:opacity-50"
                style={{
                  borderColor: "var(--sp-border)",
                  color: "var(--sp-error)",
                }}
              >
                {busyAction === "reject" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <Shield className="h-3.5 w-3.5" aria-hidden />
                )}
                Reject
              </button>
              <button
                type="button"
                onClick={doVerify}
                disabled={!!busyAction || user.status === "verified"}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold transition disabled:opacity-50"
                style={{
                  background: "var(--sp-lime)",
                  color: "var(--sp-lime-fg)",
                }}
              >
                {busyAction === "verify" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                )}
                Verify
              </button>
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="sp-chip"
              >
                <Pencil className="h-3.5 w-3.5" aria-hidden /> Edit
              </button>
            </>
          )}
        </div>
      </div>

      {err && (
        <div
          className="sp-airy mt-5 p-4 text-[13px]"
          style={{ color: "var(--sp-error)" }}
        >
          {err}
        </div>
      )}

      {/* Identity card */}
      <section className="sp-airy mt-6 p-6">
        <div className="flex flex-wrap items-start gap-4">
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-[14px] font-semibold"
            style={{ background: "var(--sp-lime-14)", color: "var(--sp-lime)" }}
          >
            {initials || "?"}
          </div>
          <div className="min-w-0 flex-1">
            {editing ? (
              <input
                type="text"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="Business name"
                className="w-full rounded-field px-3 py-2 text-[18px] font-semibold"
                style={{
                  background: "var(--sp-card-2)",
                  color: "var(--sp-text)",
                  border: "1px solid var(--sp-border)",
                }}
              />
            ) : (
              <p
                className="text-[22px] font-semibold tracking-[-0.015em]"
                style={{ color: "var(--sp-text)" }}
              >
                {user.businessName || "— no business name —"}
              </p>
            )}
            <p
              className="mt-1 text-[13px]"
              style={{ color: "var(--sp-text-2)" }}
            >
              {user.email}
            </p>
            <div
              className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px]"
              style={{ color: "var(--sp-text-3)" }}
            >
              <StatusPill status={user.status} />
              {(user.profile?.country as string | undefined) && (
                <span>{user.profile?.country as string}</span>
              )}
              <span>
                Joined {new Date(user.createdAt).toLocaleDateString()}
              </span>
              <span>
                Email {user.emailVerifiedAt ? "verified" : "not verified"}
              </span>
              <span>{user.productCount} products</span>
            </div>
          </div>
        </div>
      </section>

      {/* Verification band — approve/reject timeline + rejection note */}
      <VerificationBand user={user} />

      {/* Mandatory fields — grouped so the admin can judge the badge at a glance */}
      <SectionCard
        title={`Mandatory fields · ${MANDATORY_FIELDS_LIST.length - user.missingMandatoryFields.length}/${MANDATORY_FIELDS_LIST.length} filled`}
        subtitle="Required to earn the Verified badge."
      >
        <MixedFieldGrid
          fields={MANDATORY_FIELDS_LIST}
          missing={user.missingMandatoryFields}
          profileValues={editing ? profileDraft : (user.profile ?? {})}
          businessValues={editing ? businessDraft : (user.businessProfile ?? {})}
          editing={editing}
          onChangeProfile={(k, v) => setProfileDraft((p) => ({ ...p, [k]: v }))}
          onChangeBusiness={(k, v) => setBusinessDraft((p) => ({ ...p, [k]: v }))}
        />
      </SectionCard>

      {/* Optional / supporting fields */}
      <SectionCard
        title="Additional profile fields"
        subtitle="Not required for the badge — kept for context and buyer messaging."
      >
        <MixedFieldGrid
          fields={OPTIONAL_FIELDS_LIST}
          missing={user.missingMandatoryFields}
          profileValues={editing ? profileDraft : (user.profile ?? {})}
          businessValues={editing ? businessDraft : (user.businessProfile ?? {})}
          editing={editing}
          onChangeProfile={(k, v) => setProfileDraft((p) => ({ ...p, [k]: v }))}
          onChangeBusiness={(k, v) => setBusinessDraft((p) => ({ ...p, [k]: v }))}
        />
      </SectionCard>

      {/* Verification docs */}
      <SectionCard title={`Verification documents · ${user.docs.length}`}>
        {user.docs.length === 0 ? (
          <p
            className="text-[12.5px]"
            style={{ color: "var(--sp-text-3)" }}
          >
            This user hasn&apos;t uploaded any documents yet.
          </p>
        ) : (
          <ul className="space-y-2">
            {user.docs.map((d) => (
              <DocRow
                key={d.id}
                doc={d}
                onPreview={() => setPreview(d)}
                onApprove={async () => {
                  await adminApi.approveDoc(d.id);
                  await load();
                }}
                onReject={() => setRejectTarget(d)}
              />
            ))}
          </ul>
        )}
      </SectionCard>

      {preview && (
        <PreviewModal doc={preview} onClose={() => setPreview(null)} />
      )}

      <RejectReasonModal
        open={rejectTarget !== null}
        title={rejectTarget ? `Reject ${rejectTarget.certType}?` : ""}
        subtitle={
          rejectTarget
            ? `User will see this reason the next time they log in.`
            : undefined
        }
        onClose={() => setRejectTarget(null)}
        onSubmit={async (reason) => {
          if (!rejectTarget) return;
          await adminApi.rejectDoc(rejectTarget.id, reason);
          await load();
        }}
      />

      <RejectReasonModal
        open={rejectUser}
        onClose={() => setRejectUser(false)}
        onSubmit={doReject}
        title="Reject Verified-badge application"
        subtitle={`${user.businessName || "This user"} will see this note on their next login.`}
        quickReasons={[
          "Legal company name doesn't match what we can verify online.",
          "Phone number looks personal — please provide a business line.",
          "Operating countries list is empty or clearly incorrect.",
          "Position / role is missing or appears not to be a decision-making title.",
          "Industry mismatch with the trade position you selected.",
        ]}
        submitLabel="Reject user"
      />
    </div>
  );
}

// ── Verification band ───────────────────────────────────────────────

function VerificationBand({ user }: { user: UserDetail }) {
  const total = 7; // mirror of backend's MANDATORY_FIELDS length
  const filled = total - user.missingMandatoryFields.length;
  return (
    <section className="sp-airy mt-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <p
          className="text-[11px] font-bold uppercase tracking-[0.12em]"
          style={{ color: "var(--sp-text-3)" }}
        >
          Verified badge
        </p>
        <StatusPill status={user.status} />
        <span
          className="text-[11.5px]"
          style={{ color: "var(--sp-text-3)" }}
        >
          {filled} / {total} mandatory fields filled
        </span>
        {user.verificationSubmittedAt && (
          <span
            className="text-[11.5px]"
            style={{ color: "var(--sp-text-3)" }}
          >
            · Submitted {new Date(user.verificationSubmittedAt).toLocaleString()}
          </span>
        )}
        {user.verifiedAt && (
          <span
            className="text-[11.5px]"
            style={{ color: "var(--sp-text-3)" }}
          >
            · Approved {new Date(user.verifiedAt).toLocaleString()}
          </span>
        )}
      </div>
      {user.status === "rejected" && user.verificationRejectedReason && (
        <div
          className="mt-3 rounded-field p-3 text-[12.5px]"
          style={{
            background: "rgba(229,107,111,0.1)",
            color: "var(--sp-error)",
            border: "1px solid rgba(229,107,111,0.3)",
          }}
        >
          <span className="font-semibold">Previous rejection reason: </span>
          {user.verificationRejectedReason}
        </div>
      )}
    </section>
  );
}

// ── Mixed field grid ─────────────────────────────────────────────────

function MixedFieldGrid({
  fields,
  missing,
  profileValues,
  businessValues,
  editing,
  onChangeProfile,
  onChangeBusiness,
}: {
  fields: AdminField[];
  missing: string[];
  profileValues: Record<string, unknown>;
  businessValues: Record<string, unknown>;
  editing: boolean;
  onChangeProfile: (key: string, value: unknown) => void;
  onChangeBusiness: (key: string, value: unknown) => void;
}) {
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {fields.map((f) => {
        const values = f.source === "profile" ? profileValues : businessValues;
        const onChange =
          f.source === "profile" ? onChangeProfile : onChangeBusiness;
        const raw = values[f.key];
        const display =
          raw === null || raw === undefined || raw === ""
            ? ""
            : Array.isArray(raw)
            ? raw.join(", ")
            : String(raw);
        const isMandatory = MANDATORY_KEYS.has(f.key);
        const isFilled = !missing.includes(f.key);
        return (
          <div
            key={f.key}
            className={f.cols === 2 ? "sm:col-span-2" : undefined}
          >
            <div className="flex items-center gap-2">
              <span
                className="text-[10.5px] font-bold uppercase tracking-[0.1em]"
                style={{ color: "var(--sp-text-3)" }}
              >
                {f.label}
              </span>
              {isMandatory && (
                <span
                  className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.08em]"
                  style={
                    isFilled
                      ? {
                          background: "var(--sp-lime-14)",
                          color: "var(--sp-lime)",
                        }
                      : {
                          background: "rgba(229,107,111,0.1)",
                          color: "var(--sp-error)",
                        }
                  }
                >
                  {isFilled ? "Filled" : "Not filled"}
                </span>
              )}
            </div>
            {editing ? (
              f.type === "textarea" ? (
                <textarea
                  value={display}
                  onChange={(e) => onChange(f.key, e.target.value)}
                  rows={3}
                  className="mt-1.5 w-full rounded-field px-3 py-2 text-[13px]"
                  style={{
                    background: "var(--sp-card-2)",
                    color: "var(--sp-text)",
                    border: "1px solid var(--sp-border)",
                  }}
                />
              ) : (
                <input
                  type="text"
                  value={display}
                  onChange={(e) =>
                    onChange(
                      f.key,
                      f.key === "operatingCountries" ||
                        f.key === "targetMarkets" ||
                        f.key === "targetBuyerTypes"
                        ? e.target.value
                            .split(",")
                            .map((x) => x.trim())
                            .filter(Boolean)
                        : e.target.value,
                    )
                  }
                  className="mt-1.5 w-full rounded-field px-3 py-2 text-[13px]"
                  style={{
                    background: "var(--sp-card-2)",
                    color: "var(--sp-text)",
                    border: "1px solid var(--sp-border)",
                  }}
                />
              )
            ) : display === "" ? (
              <p
                className="mt-1.5 text-[13px] italic"
                style={{ color: "var(--sp-text-3)" }}
              >
                — not filled —
              </p>
            ) : (
              <p
                className="mt-1.5 text-[13px]"
                style={{ color: "var(--sp-text)" }}
              >
                {display}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────

function cleanDraft(d: Record<string, unknown>, allowed: string[]) {
  const out: Record<string, unknown> = {};
  for (const k of allowed) {
    if (k in d) out[k] = d[k] ?? "";
  }
  return out;
}

function SectionCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="sp-airy mt-4 p-6">
      <p
        className="text-[11px] font-bold uppercase tracking-[0.12em]"
        style={{ color: "var(--sp-text-3)" }}
      >
        {title}
      </p>
      {subtitle && (
        <p
          className="mt-1 text-[11.5px]"
          style={{ color: "var(--sp-text-3)" }}
        >
          {subtitle}
        </p>
      )}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function StatusPill({ status }: { status: string }) {
  const label = status.replace(/_/g, " ");
  const tone =
    status === "verified"
      ? { bg: "var(--sp-lime-14)", fg: "var(--sp-lime)" }
      : status === "rejected"
      ? { bg: "rgba(229,107,111,0.12)", fg: "var(--sp-error)" }
      : status === "active"
      ? { bg: "rgba(126,159,255,0.12)", fg: "var(--sp-info)" }
      : { bg: "var(--sp-card-2)", fg: "var(--sp-text-2)" };
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em]"
      style={{ background: tone.bg, color: tone.fg }}
    >
      {label}
    </span>
  );
}

function DocRow({
  doc,
  onPreview,
  onApprove,
  onReject,
}: {
  doc: VerifyDoc;
  onPreview: () => void;
  onApprove: () => Promise<void>;
  onReject: () => void;
}) {
  const Icon = doc.mimeType.startsWith("image/") ? ImageIcon : FileText;
  const sizeKb = Math.round(doc.sizeBytes / 1024);
  const [busy, setBusy] = useState(false);
  const tone =
    doc.status === "approved"
      ? { bg: "var(--sp-lime-14)", fg: "var(--sp-lime)" }
      : doc.status === "rejected"
      ? { bg: "rgba(229,107,111,0.12)", fg: "var(--sp-error)" }
      : { bg: "rgba(139,92,246,0.14)", fg: "#9f75ff" };

  return (
    <li
      className="rounded-[14px] p-3"
      style={{
        background: "var(--sp-card-2)",
        border: "1px solid var(--sp-border)",
      }}
    >
    <div className="flex flex-wrap items-center gap-3">
      <Icon
        className="h-4 w-4 shrink-0"
        aria-hidden
        style={{ color: "var(--sp-text-2)" }}
      />
      <div className="min-w-0 flex-1">
        <p
          className="text-[13px] font-semibold"
          style={{ color: "var(--sp-text)" }}
        >
          {doc.certType}
        </p>
        <button
          type="button"
          onClick={onPreview}
          className="truncate text-[11.5px] hover:underline"
          style={{ color: "var(--sp-text-2)" }}
        >
          {doc.filename} · {sizeKb} KB
        </button>
      </div>
      <span
        className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em]"
        style={{ background: tone.bg, color: tone.fg }}
      >
        {doc.status}
      </span>
      <a
        href={`${API_BASE}${doc.url}`}
        download={doc.filename}
        className="sp-icon-btn"
        style={{ height: "32px", width: "32px" }}
        aria-label={`Download ${doc.filename}`}
      >
        <Download className="h-3.5 w-3.5" aria-hidden />
      </a>
      {doc.status === "pending" && (
        <>
          <button
            type="button"
            onClick={onReject}
            className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold disabled:opacity-50"
            style={{
              borderColor: "var(--sp-border)",
              color: "var(--sp-error)",
            }}
          >
            <X className="h-3 w-3" aria-hidden /> Reject
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onApprove();
              } finally {
                setBusy(false);
              }
            }}
            className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold disabled:opacity-50"
            style={{
              background: "var(--sp-lime)",
              color: "var(--sp-lime-fg)",
            }}
          >
            {busy ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
            ) : (
              <Check className="h-3 w-3" aria-hidden />
            )}
            Approve
          </button>
        </>
      )}
    </div>
    {doc.status === "rejected" && doc.rejectionReason && (
      <p
        className="mt-2 text-[11.5px] leading-relaxed"
        style={{ color: "var(--sp-error)" }}
      >
        <span className="font-semibold">Reason:</span> {doc.rejectionReason}
      </p>
    )}
    </li>
  );
}

function PreviewModal({
  doc,
  onClose,
}: {
  doc: VerifyDoc;
  onClose: () => void;
}) {
  const src = `${API_BASE}${doc.url}`;
  const isImage = doc.mimeType.startsWith("image/");
  const isPdf = doc.mimeType === "application/pdf";
  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-3xl rounded-[22px] overflow-hidden"
        style={{
          background: "var(--sp-card)",
          border: "1px solid var(--sp-border)",
        }}
      >
        <div
          className="flex items-center justify-between p-4"
          style={{ borderBottom: "1px solid var(--sp-border)" }}
        >
          <p
            className="truncate text-[14px] font-semibold"
            style={{ color: "var(--sp-text)" }}
          >
            {doc.filename}
          </p>
          <div className="flex items-center gap-2">
            <a
              href={src}
              download={doc.filename}
              className="sp-icon-btn"
              aria-label="Download"
            >
              <Download className="h-4 w-4" aria-hidden />
            </a>
            <button
              type="button"
              onClick={onClose}
              className="sp-icon-btn"
              aria-label="Close preview"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
        <div style={{ background: "var(--sp-canvas)", height: "70vh" }}>
          {isImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={src}
              alt={doc.filename}
              className="h-full w-full object-contain"
            />
          ) : isPdf ? (
            <iframe
              src={src}
              title={doc.filename}
              className="h-full w-full"
              style={{ border: 0 }}
            />
          ) : (
            <div
              className="flex h-full flex-col items-center justify-center gap-3 text-[13px]"
              style={{ color: "var(--sp-text-2)" }}
            >
              <FileText className="h-10 w-10" aria-hidden />
              Preview not available. Use the download button above.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
