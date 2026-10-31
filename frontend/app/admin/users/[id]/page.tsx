"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  adminApi,
  errorMessage,
  errorStatus,
  isBusinessListKey,
  type BusinessPatch,
  type BusinessPatchKey,
  type ProfilePatch,
  type ProfilePatchKey,
  type UserDetail,
  type UserPatch,
  type VerifyDoc,
} from "@/lib/adminApi";
import { ENTITY_TYPE_LABELS, entityTypeLabel } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useUnsavedGuard } from "@/lib/useUnsavedGuard";
import { fieldByKey } from "@/lib/verification";
import { useTower } from "@/components/shell/TowerShell";
import { Stagger, StaggerItem } from "@/components/motion";
import { Button, LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { HoldButton, Progress } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Card, EmptyState, Notice, SectionTitle, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { OnboardingTimeline } from "@/components/admin/OnboardingTimeline";
import {
  DOC_REJECT_REASONS,
  RejectSheet,
  USER_REJECT_REASONS,
} from "@/components/admin/RejectSheet";
import { DocCard, KeyValue, StatusChip } from "@/components/admin/parts";
import { displayValue, fmtDate, fmtDateTime, plural, refId, tradeLabel } from "@/components/admin/format";

/* ───────────────────────────── Field layout ─────────────────────────
   Mandatory (Verified-badge) fields first so the decision reads at a
   glance; everything else below. `source` picks the draft bucket, so one
   grid can mix profile and business fields. Keys mirror the backend's
   editable whitelists (see PROFILE_PATCH_KEYS / BUSINESS_PATCH_KEYS). */

type FieldMeta = { label: string; kind?: FieldKind; wide?: boolean; mono?: boolean; hint?: string };
type FieldDef =
  | ({ source: "profile"; key: ProfilePatchKey } & FieldMeta)
  | ({ source: "business"; key: BusinessPatchKey } & FieldMeta);
type FieldKind = "text" | "textarea" | "list" | "trade" | "entity" | "tel" | "url";

/** Profile fields required for KYB (required documents come from the server). */
const MANDATORY_FIELDS: FieldDef[] = [
  { key: "legalName", label: "Company name", source: "business" },
  { key: "addressLine", label: "Registered address", source: "business", wide: true },
  { key: "city", label: "City", source: "business" },
  { key: "country", label: "Country", source: "business", mono: true, hint: "2-letter code, e.g. IN or AE." },
];

const OPTIONAL_FIELDS: FieldDef[] = [
  { key: "fullName", label: "Full name", source: "profile" },
  { key: "position", label: "Position", source: "profile" },
  { key: "phone", label: "Phone", source: "profile", kind: "tel", mono: true },
  { key: "industry", label: "Industry", source: "business" },
  { key: "operatingCountries", label: "Operating countries", source: "business", kind: "list" },
  { key: "tradePosition", label: "Trade position", source: "business", kind: "trade" },
  { key: "entityType", label: "Entity type", source: "business", kind: "entity" },
  { key: "websiteUrl", label: "Website", source: "business", kind: "url" },
  { key: "state", label: "State", source: "business" },
  { key: "pincode", label: "Pincode", source: "business", mono: true },
  { key: "googleBusinessUrl", label: "Google Business", source: "business", kind: "url" },
  { key: "facebookUrl", label: "Facebook", source: "business", kind: "url" },
  { key: "sellerType", label: "Seller type", source: "business" },
  { key: "exportStatus", label: "Export status", source: "business" },
  { key: "targetMarkets", label: "Target markets", source: "business", kind: "list" },
  { key: "companyIntroduction", label: "Company introduction", source: "business", kind: "textarea", wide: true },
];

const ALL_FIELDS = [...MANDATORY_FIELDS, ...OPTIONAL_FIELDS];

const TRADE_OPTIONS = [
  { value: "", label: "Not set" },
  { value: "buyer", label: "Buyer" },
  { value: "seller", label: "Seller" },
  { value: "both", label: "Buyer & seller" },
];

const ENTITY_OPTIONS = [
  { value: "", label: "Not set" },
  ...Object.entries(ENTITY_TYPE_LABELS).map(([value, label]) => ({ value, label })),
];

const fid = (f: FieldDef) => `${f.source}.${f.key}`;

function sourceOf(u: UserDetail, f: FieldDef): unknown {
  return (f.source === "profile" ? u.profile : u.businessProfile)?.[f.key];
}

/** Draft strings for every editable field (lists as "a, b, c"). */
function draftFrom(u: UserDetail): Record<string, string> {
  const d: Record<string, string> = {};
  for (const f of ALL_FIELDS) d[fid(f)] = displayValue(sourceOf(u, f));
  return d;
}

const splitList = (s: string) =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

const norm = (f: FieldDef, s: string) => (f.kind === "list" ? splitList(s).join("\u0000") : s.trim());

/** Only changed keys, typed exactly as the backend expects. */
function buildPatch(u: UserDetail, draft: Record<string, string>): { patch: UserPatch; count: number } {
  const orig = draftFrom(u);
  const patch: UserPatch = {};
  const profile: ProfilePatch = {};
  const business: BusinessPatch = {};
  let count = 0;

  for (const f of ALL_FIELDS) {
    const k = fid(f);
    if (norm(f, draft[k] ?? "") === norm(f, orig[k] ?? "")) continue;
    count++;
    if (f.source === "profile") {
      profile[f.key] = (draft[k] ?? "").trim();
    } else if (isBusinessListKey(f.key)) {
      business[f.key] = splitList(draft[k] ?? "");
    } else if (f.key === "entityType") {
      // An enum: clearing it means null, never "".
      business.entityType = (draft[k] ?? "").trim() || null;
    } else {
      business[f.key] = (draft[k] ?? "").trim();
    }
  }
  if (Object.keys(profile).length) patch.profile = profile;
  if (Object.keys(business).length) patch.businessProfile = business;
  return { patch, count };
}

/** Put a server message next to the field it's about, when we can tell. */
function fieldForError(msg: string): string | null {
  for (const f of ALL_FIELDS) if (msg.includes(f.key)) return fid(f);
  if (/phone/i.test(msg)) return "profile.phone";
  if (/website/i.test(msg)) return "business.websiteUrl";
  if (/legal|company name/i.test(msg)) return "business.legalName";
  return null;
}

const APPROVABLE = new Set(["pending_verification", "rejected"]);
const REJECTABLE = new Set(["pending_verification", "verified"]);

/* ───────────────────────────── Page ───────────────────────────────── */

export default function AccountDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const { refreshStats, can } = useTower();
  const toast = useToast();
  const { setDirty } = useUnsavedGuard();

  const [user, setUser] = useState<UserDetail | null>(null);
  const [loadErr, setLoadErr] = useState<{ msg: string; status?: number } | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [fieldErr, setFieldErr] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [rejectUserOpen, setRejectUserOpen] = useState(false);
  const [rejectDoc, setRejectDoc] = useState<VerifyDoc | null>(null);
  const [docBusy, setDocBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const u = await adminApi.user(id);
      setUser(u);
      setLoadErr(null);
      return u;
    } catch (e) {
      setLoadErr({ msg: errorMessage(e, "Couldn't load this account."), status: errorStatus(e) });
      return null;
    }
  }, [id]);

  useEffect(() => {
    if (id) void load();
  }, [id, load]);

  const { patch, count: changeCount } = useMemo(
    () => (user && editing ? buildPatch(user, draft) : { patch: {}, count: 0 }),
    [user, editing, draft],
  );

  useEffect(() => {
    setDirty(editing && changeCount > 0);
  }, [editing, changeCount, setDirty]);
  useEffect(() => () => setDirty(false), [setDirty]);

  const startEdit = () => {
    if (!user) return;
    setDraft(draftFrom(user));
    setSaveErr(null);
    setFieldErr({});
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setSaveErr(null);
    setFieldErr({});
  };

  const setField = (k: string, v: string) => {
    setDraft((d) => ({ ...d, [k]: v }));
    if (fieldErr[k]) {
      setFieldErr((errs) => {
        const next = { ...errs };
        delete next[k];
        return next;
      });
    }
  };

  const save = async () => {
    if (!user) return;
    if (changeCount === 0) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setSaveErr(null);
    setFieldErr({});
    try {
      const updated = await adminApi.patchUser(user.userId, patch);
      setUser(updated);
      setEditing(false);
      toast(`Saved ${plural(changeCount, "change")}`, "verified");
      void refreshStats();
    } catch (e) {
      const msg = errorMessage(e, "Save failed.");
      const status = errorStatus(e);
      const where = fieldForError(msg);
      if (where) setFieldErr({ [where]: msg });
      setSaveErr(status === 409 ? `Already taken — ${msg}` : msg);
      toast(status === 409 ? "Duplicate found — not saved" : "Not saved", "frozen");
    } finally {
      setSaving(false);
    }
  };

  const approve = async () => {
    if (!user) return;
    setBusy(true);
    setActionErr(null);
    try {
      await adminApi.verifyUser(user.userId);
      toast(`${user.businessName || user.email} verified`, "verified");
      await load();
      void refreshStats();
    } catch (e) {
      const msg = errorMessage(e, "Approve failed.");
      setActionErr(msg);
      toast(msg, "frozen");
    } finally {
      setBusy(false);
    }
  };

  const rejectUser = async (reason: string) => {
    if (!user) return;
    await adminApi.rejectUser(user.userId, reason);
    toast(`${user.businessName || user.email} ${user.status === "verified" ? "badge revoked" : "rejected"}`);
    setActionErr(null);
    await load();
    void refreshStats();
  };

  const approveDoc = async (doc: VerifyDoc) => {
    setDocBusy(doc.id);
    try {
      await adminApi.approveDoc(doc.id);
      toast(`${doc.certType} approved`, "verified");
      await load();
      void refreshStats();
    } catch (e) {
      toast(errorMessage(e, "Approve failed."), "frozen");
    } finally {
      setDocBusy(null);
    }
  };

  const rejectDocSubmit = async (reason: string) => {
    if (!rejectDoc) return;
    await adminApi.rejectDoc(rejectDoc.id, reason);
    toast(`${rejectDoc.certType} rejected`);
    await load();
    void refreshStats();
  };

  const closeRejectUser = useCallback(() => setRejectUserOpen(false), []);
  const closeRejectDoc = useCallback(() => setRejectDoc(null), []);

  /* ── States ── */

  if (!user && loadErr) {
    return (
      <div className="pt-4">
        <BackLink />
        <Card className="mt-6 p-2">
          {loadErr.status === 404 ? (
            <EmptyState
              icon="users"
              title="Account not found"
              action={<LinkButton href="/admin/users" variant="secondary">Back to directory</LinkButton>}
            >
              It may have been deleted, or the link is wrong.
            </EmptyState>
          ) : (
            <EmptyState
              icon="alert"
              title="Couldn't load this account"
              action={<Button variant="secondary" onClick={() => void load()}>Try again</Button>}
            >
              {loadErr.msg}
            </EmptyState>
          )}
        </Card>
      </div>
    );
  }

  if (!user) return <DetailSkeleton />;

  const missing = user.missingMandatoryFields;
  const MANDATORY_TOTAL = MANDATORY_FIELDS.length + missing.filter((k) => k.startsWith("kyb:")).length;
  const filled = MANDATORY_TOTAL - missing.length;
  const title = user.businessName || displayValue(user.businessProfile?.legalName) || user.email;
  const passportPlace = [displayValue(user.businessProfile?.city), displayValue(user.businessProfile?.country)]
    .filter(Boolean)
    .join(", ");
  const canApprove = APPROVABLE.has(user.status) && missing.length === 0 && !editing;
  const canReject = REJECTABLE.has(user.status) && !editing;
  const approveHint = editing
    ? "Save or cancel your edits first."
    : missing.length
      ? `${plural(missing.length, "required item")} still missing.`
      : user.status === "verified"
        ? "Already verified."
        : !APPROVABLE.has(user.status)
          ? "Not submitted for review yet — they submit from their account."
          : null;

  return (
    <div className={cn("pt-4", editing && "pb-24")}>
      <BackLink />

      {/* ── Passport: who this is, where they stand, the decision ── */}
      <section
        aria-labelledby="passport-h"
        className="relief relative mt-6 animate-rise overflow-hidden rounded-[34px] p-6 sm:p-9"
      >
        <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -left-20 size-96 rounded-full bg-lime/[0.08] blur-3xl" />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-28 size-80 rounded-full blur-3xl"
          style={{ background: "radial-gradient(closest-side, rgb(255 196 130 / 0.08), transparent)" }}
        />

        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2.5">
              <p className="t-label text-accent">
                Corridor passport{passportPlace ? ` · ${passportPlace}` : ""}
              </p>
              {editing ? <Chip tone="move" icon="pen" size="sm">Editing</Chip> : null}
            </div>
            <h1 id="passport-h" className="t-large mt-3 break-words text-fg">
              {title}
            </h1>
            <p className="t-callout mt-2 break-words text-fg-2">
              {user.email}
              <span className="text-fg-3">
                {" "}
                · joined {fmtDate(user.createdAt)} · {plural(user.productCount, "product")}
              </span>
            </p>
          </div>
          <div className="flex items-start gap-5">
            <div className="text-right">
              <p className="t-label text-fg-3">Ref</p>
              <p className="t-code mt-1 text-[22px] text-fg" title={user.userId}>
                {refId("USR", user.userId)}
              </p>
            </div>
            {!editing ? (
              <Button variant="secondary" size="sm" icon="pen" onClick={startEdit}>
                Edit
              </Button>
            ) : null}
          </div>
        </div>

        <dl className="relative mt-8 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-line pt-6 lg:grid-cols-4">
          <div className="min-w-0">
            <dt className="t-label text-fg-3">Status</dt>
            <dd className="mt-2">
              <StatusChip status={user.status} />
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="t-label text-fg-3">Mandatory fields</dt>
            <dd className="mt-1.5">
              <span className="tabular text-[20px] font-medium tracking-[-0.025em] text-fg">
                {filled}
                <span className="text-fg-3"> / {MANDATORY_TOTAL}</span>
              </span>
              <Progress value={filled} max={MANDATORY_TOTAL} label="Required items in" className="mt-2 max-w-[180px]" />
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="t-label text-fg-3">Submitted</dt>
            <dd className="t-callout mt-2 text-fg">
              {user.verificationSubmittedAt ? fmtDateTime(user.verificationSubmittedAt) : <span className="text-fg-3">Not yet</span>}
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="t-label text-fg-3">Approved</dt>
            <dd className="t-callout mt-2 text-fg">
              {user.verifiedAt ? fmtDateTime(user.verifiedAt) : <span className="text-fg-3">—</span>}
            </dd>
          </div>
        </dl>

        {/* The decision */}
        <div className="relative mt-7 flex flex-col gap-4 rounded-[24px] bg-white/[0.03] p-4 shadow-[inset_0_0_0_1px_var(--c-line)] sm:p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <h2 className="t-headline flex items-center gap-2 text-fg">
              <Icon name="shield" size={16} className="text-accent" />
              Verified badge
            </h2>
            <p className="t-sub mt-1 text-fg-3">
              {approveHint ??
                (user.status === "verified"
                  ? "Verified. Revoke it if something no longer holds."
                  : "Profile and required documents are in — hold to approve.")}
            </p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center">
            <Button variant="danger" icon="close" onClick={() => setRejectUserOpen(true)} disabled={!canReject || busy}>
              {user.status === "verified" ? "Revoke…" : "Reject…"}
            </Button>
            <HoldButton tone="commit" icon="shield" onCommit={approve} loading={busy} disabled={!canApprove}>
              Approve
            </HoldButton>
          </div>
        </div>

        {missing.length || user.verificationRejectedReason || actionErr ? (
          <div className="relative mt-4 flex flex-col gap-3">
            {missing.length ? (
              <Notice tone="move" title="Empty mandatory fields">
                {missing.map((k) => fieldByKey(k)?.label ?? k).join(", ")}.
              </Notice>
            ) : null}
            {user.verificationRejectedReason ? (
              <Notice tone="frozen" title={user.status === "rejected" ? "Rejected — reason sent" : "Previous rejection"}>
                {user.verificationRejectedReason}
              </Notice>
            ) : null}
            {actionErr ? <Notice tone="frozen">{actionErr}</Notice> : null}
          </div>
        ) : null}
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        {/* ── Main column ── */}
        <div className="flex min-w-0 flex-col gap-6">
          {saveErr ? (
            <Notice tone="frozen" title="Not saved">
              {saveErr}
            </Notice>
          ) : null}

          <Card as="section" aria-labelledby="mand-h" className="p-6 sm:p-7">
            <SectionTitle
              title={<span id="mand-h">Mandatory fields</span>}
              meta={`${filled}/${MANDATORY_TOTAL} filled`}
            />
            <p className="t-sub mt-1 text-fg-3">Required for the Verified badge.</p>
            <FieldGrid
              fields={MANDATORY_FIELDS}
              user={user}
              editing={editing}
              draft={draft}
              errors={fieldErr}
              missing={missing}
              onChange={setField}
            />
          </Card>

          <Card as="section" aria-labelledby="opt-h" className="p-6 sm:p-7">
            <SectionTitle title={<span id="opt-h">Additional details</span>} />
            <p className="t-sub mt-1 text-fg-3">Not needed for the badge — context for reviews and buyers.</p>
            <FieldGrid
              fields={OPTIONAL_FIELDS}
              user={user}
              editing={editing}
              draft={draft}
              errors={fieldErr}
              missing={missing}
              onChange={setField}
            />
          </Card>

          <section aria-labelledby="docs-h">
            <div className="flex items-end justify-between gap-4">
              <h2 id="docs-h" className="t-title2 text-fg">
                Documents
              </h2>
              {user.docs.length ? (
                <p className="t-sub text-fg-3">
                  {user.docs.filter((d) => d.status === "approved").length} of {user.docs.length} approved
                  {user.docs.some((d) => d.status === "pending")
                    ? ` · ${user.docs.filter((d) => d.status === "pending").length} to check`
                    : ""}
                </p>
              ) : null}
            </div>
            {user.docs.length === 0 ? (
              <Card className="mt-5 p-2">
                <EmptyState icon="doc-check" title="No documents" className="py-10">
                  Nothing uploaded yet. Documents are optional for the badge.
                </EmptyState>
              </Card>
            ) : (
              <Stagger as="ul" className="mt-5 grid gap-4 sm:grid-cols-2">
                {user.docs.map((d) => (
                  <StaggerItem as="li" key={d.id} className="flex">
                    <DocCard
                      doc={d}
                      actions={
                        d.status === "pending" ? (
                          <>
                            <Button variant="danger" size="sm" onClick={() => setRejectDoc(d)} disabled={docBusy === d.id}>
                              Reject…
                            </Button>
                            <HoldButton
                              tone="commit"
                              size="sm"
                              onCommit={() => approveDoc(d)}
                              loading={docBusy === d.id}
                              holdMs={900}
                            >
                              Approve
                            </HoldButton>
                          </>
                        ) : null
                      }
                    />
                  </StaggerItem>
                ))}
              </Stagger>
            )}
          </section>
        </div>

        {/* ── Aside ── */}
        <aside className="flex min-w-0 flex-col gap-6 lg:sticky lg:top-6">
          <Card as="section" aria-labelledby="tl-h" className="p-6">
            <h2 id="tl-h" className="t-label text-fg-3">
              Onboarding
            </h2>
            <OnboardingTimeline user={user} className="mt-5" />
          </Card>

          <Card as="section" aria-labelledby="acct-h" className="p-6">
            <h2 id="acct-h" className="t-label text-fg-3">
              Account
            </h2>
            <dl className="mt-5 grid gap-4">
              <KeyValue label="Account ID" value={user.userId} mono />
              <KeyValue label="Business ID" value={user.businessId} mono />
              <KeyValue label="Role" value={user.role.charAt(0).toUpperCase() + user.role.slice(1)} />
              <KeyValue label="Email" value={user.email} />
              <KeyValue label="Email confirmed" value={user.emailVerifiedAt ? fmtDateTime(user.emailVerifiedAt) : "Not yet"} />
              <KeyValue label="Products" value={String(user.productCount)} />
              <KeyValue label="Updated" value={fmtDateTime(user.updatedAt)} />
            </dl>
          </Card>

          {user.security ? (
            <SecurityCard
              userId={user.userId}
              security={user.security}
              canAct={can("accounts.security")}
              onChanged={load}
            />
          ) : null}
        </aside>
      </div>

      {/* Floating save bar — stays above the dock on phones. */}
      {editing ? (
        <div className="pointer-events-none fixed inset-x-0 bottom-[calc(max(12px,env(safe-area-inset-bottom))+76px)] z-30 flex justify-center px-4 md:bottom-6 md:pl-[108px]">
          <div
            role="region"
            aria-label="Unsaved changes"
            className="glass pointer-events-auto flex items-center gap-3 rounded-full py-2 pl-5 pr-2"
          >
            <span className={cn("t-sub", changeCount ? "text-fg" : "text-fg-3")}>
              {changeCount ? `${plural(changeCount, "change")} unsaved` : "No changes yet"}
            </span>
            <Button variant="quiet" size="sm" onClick={cancelEdit} disabled={saving}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={() => void save()} loading={saving} disabled={changeCount === 0}>
              Save
            </Button>
          </div>
        </div>
      ) : null}

      <RejectSheet
        open={rejectUserOpen}
        onClose={closeRejectUser}
        title={user.status === "verified" ? "Revoke the Verified badge?" : "Reject this application?"}
        description={`${user.businessName || "They"} will see your reason on their next sign-in.`}
        quickReasons={USER_REJECT_REASONS}
        submitLabel={user.status === "verified" ? "Revoke" : "Reject"}
        onSubmit={rejectUser}
      />
      <RejectSheet
        open={rejectDoc !== null}
        onClose={closeRejectDoc}
        title={rejectDoc ? `Reject ${rejectDoc.certType}?` : "Reject document"}
        description="They'll see your reason and can upload a new file."
        quickReasons={DOC_REJECT_REASONS}
        submitLabel="Reject"
        onSubmit={rejectDocSubmit}
      />
    </div>
  );
}

/* ───────────────────────────── Pieces ─────────────────────────────── */

/** Sign-in state: lockout, the one active device; support can unlock / sign out. */
function SecurityCard({
  userId,
  security,
  canAct,
  onChanged,
}: {
  userId: string;
  security: NonNullable<UserDetail["security"]>;
  canAct: boolean;
  onChanged: () => Promise<unknown> | void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<"unlock" | "signout" | null>(null);
  const run = async (kind: "unlock" | "signout") => {
    setBusy(kind);
    try {
      if (kind === "unlock") await adminApi.unlockUser(userId);
      else await adminApi.signOutUser(userId);
      toast(kind === "unlock" ? "Account unlocked" : "Signed out of their device", "verified");
      await onChanged();
    } catch (e) {
      toast(errorMessage(e, "That didn't work."), "frozen");
    } finally {
      setBusy(null);
    }
  };
  const lock =
    security.lockState === "support"
      ? "Locked — waiting for support"
      : security.lockState === "temporary"
        ? `Locked until ${security.lockedUntil ? fmtDateTime(security.lockedUntil) : "soon"}`
        : "Not locked";
  const s = security.activeSession;
  return (
    <Card as="section" aria-labelledby="sec-h" className="p-6">
      <h2 id="sec-h" className="t-label text-fg-3">
        Sign-in &amp; security
      </h2>
      {security.lockState !== "none" ? (
        <div className="mt-4">
          <Notice tone="frozen">
            {security.lockState === "support"
              ? "Locked after three rounds of failed sign-ins. Confirm who you’re talking to before unlocking."
              : "Temporarily locked after five wrong passwords."}
          </Notice>
        </div>
      ) : null}
      <dl className="mt-5 grid gap-4">
        <KeyValue label="Lock" value={lock} />
        <KeyValue label="Wrong passwords" value={String(security.failedLoginCount)} />
        <KeyValue label="Last sign-in" value={security.lastLoginAt ? fmtDateTime(security.lastLoginAt) : "Never"} />
        <KeyValue
          label="Signed-in device"
          value={s ? `${s.ipPrefix ?? "unknown network"} · active ${fmtDateTime(s.lastSeenAt)}` : "None"}
        />
      </dl>
      {canAct ? (
        <div className="mt-5 flex flex-wrap gap-2">
          {security.lockState !== "none" ? (
            <Button size="sm" variant="secondary" icon="unlock" loading={busy === "unlock"} onClick={() => void run("unlock")}>
              Unlock
            </Button>
          ) : null}
          {s ? (
            <Button size="sm" variant="secondary" icon="logout" loading={busy === "signout"} onClick={() => void run("signout")}>
              Sign out device
            </Button>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

function BackLink() {
  return (
    <LinkButton href="/admin/users" variant="quiet" size="sm" icon="arrow-left" className="-ml-3">
      Directory
    </LinkButton>
  );
}

function FieldGrid({
  fields,
  user,
  editing,
  draft,
  errors,
  missing,
  onChange,
}: {
  fields: FieldDef[];
  user: UserDetail;
  editing: boolean;
  draft: Record<string, string>;
  errors: Record<string, string>;
  missing: string[];
  onChange: (key: string, value: string) => void;
}) {
  return (
    <div className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2">
      {fields.map((f) => {
        const k = fid(f);
        const mandatory = MANDATORY_FIELDS.some((m) => m.key === f.key && m.source === f.source);
        const tag = mandatory ? (
          missing.includes(f.key) ? (
            <Chip tone="move" noIcon className="h-5 px-2 text-[11px]">
              Missing
            </Chip>
          ) : (
            <Chip tone="verified" noIcon className="h-5 px-2 text-[11px]">
              Filled
            </Chip>
          )
        ) : undefined;

        if (editing) {
          const value = draft[k] ?? "";
          const common = { label: f.label, error: errors[k], action: tag, className: f.wide ? "sm:col-span-2" : undefined };
          if (f.kind === "textarea") {
            return (
              <Textarea key={k} {...common} value={value} rows={4} onChange={(e) => onChange(k, e.target.value)} />
            );
          }
          if (f.kind === "entity") {
            const opts = ENTITY_OPTIONS.some((o) => o.value === value) ? ENTITY_OPTIONS : [...ENTITY_OPTIONS, { value, label: value }];
            return <Select key={k} {...common} value={value} options={opts} onChange={(e) => onChange(k, e.target.value)} />;
          }
          if (f.kind === "trade") {
            const opts = TRADE_OPTIONS.some((o) => o.value === value) ? TRADE_OPTIONS : [...TRADE_OPTIONS, { value, label: value }];
            return <Select key={k} {...common} value={value} options={opts} onChange={(e) => onChange(k, e.target.value)} />;
          }
          return (
            <Input
              key={k}
              {...common}
              value={value}
              type={f.kind === "tel" ? "tel" : f.kind === "url" ? "url" : "text"}
              inputMode={f.kind === "tel" ? "tel" : f.kind === "url" ? "url" : undefined}
              hint={f.kind === "list" ? "Separate with commas." : f.hint}
              inputClassName={f.mono ? "font-mono text-[14px]" : undefined}
              onChange={(e) => onChange(k, e.target.value)}
            />
          );
        }

        const raw = sourceOf(user, f);
        let value: ReactNode = displayValue(raw) || null;
        if (f.kind === "trade") value = tradeLabel(displayValue(raw));
        if (f.kind === "entity") value = entityTypeLabel(displayValue(raw)) || null;
        if (f.kind === "list" && Array.isArray(raw) && raw.length) {
          value = (
            <span className="flex flex-wrap gap-1.5">
              {raw.map((c) => (
                <Chip key={String(c)} tone="quiet">
                  {String(c)}
                </Chip>
              ))}
            </span>
          );
        }
        if (f.kind === "url" && typeof raw === "string" && raw) {
          value = (
            <a
              href={/^https?:\/\//i.test(raw) ? raw : `https://${raw}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-line-2 underline-offset-4 hover:decoration-fg"
            >
              {raw}
            </a>
          );
        }
        return (
          <div key={k} className={cn("min-w-0", f.wide && "sm:col-span-2")}>
            <div className="flex items-center justify-between gap-3">
              <p className="t-label text-fg-3">{f.label}</p>
              {tag}
            </div>
            <div className={cn("mt-2 break-words text-[14.5px] leading-snug text-fg", f.mono && "t-code text-[13px]")}>
              {value ?? <span className="text-fg-3">Not filled</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="pt-4" aria-busy="true">
      <Skeleton className="h-8 w-28 rounded-full" />
      <Skeleton className="mt-6 h-[360px] rounded-[34px]" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Skeleton className="h-[360px] rounded-card" />
        <Skeleton className="h-[360px] rounded-card" />
      </div>
      <span className="sr-only">Loading account…</span>
    </div>
  );
}
