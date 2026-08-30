"use client";

import {
  Suspense,
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  Check,
  Landmark,
  MapPin,
  Pencil,
  Save,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import { adminApi, type UserDetail } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { useDirtyFlag, useUnsavedGuard } from "@/lib/useUnsavedGuard";

// ── Field taxonomy ─────────────────────────────────────────────────────────
// Each field: which section, which key on the API block, label, mono-font flag.

interface FieldSpec {
  key: string;
  label: string;
  mono?: boolean;
  wide?: boolean;
}

const BUYER_IDENTITY: FieldSpec[] = [
  { key: "fullName", label: "Full name" },
  { key: "email", label: "Email" },
  { key: "businessEmail", label: "Business email" },
  { key: "altMobile", label: "Alt mobile" },
  { key: "altEmail", label: "Alt email" },
];

const BUYER_ADDRESS: FieldSpec[] = [
  { key: "addressLine", label: "Address", wide: true },
  { key: "city", label: "City" },
  { key: "state", label: "State" },
  { key: "pincode", label: "Pincode" },
];

const BUYER_WEB: FieldSpec[] = [
  { key: "websiteUrl", label: "Website" },
  { key: "googleBusinessUrl", label: "Google Business" },
  { key: "facebookUrl", label: "Facebook" },
];

const SELLER_FIELDS: FieldSpec[] = [
  { key: "companyName", label: "Company" },
  { key: "gstin", label: "GSTIN", mono: true },
  { key: "pan", label: "PAN", mono: true },
  { key: "udyam", label: "Udyam", mono: true },
  { key: "aadhaar", label: "Aadhaar", mono: true },
  { key: "tan", label: "TAN", mono: true },
];

const BANK_FIELDS: FieldSpec[] = [
  { key: "holderName", label: "Holder" },
  { key: "bankName", label: "Bank" },
  { key: "branchName", label: "Branch" },
  { key: "ifsc", label: "IFSC", mono: true },
  { key: "accountNumber", label: "Account #", mono: true },
];

export default function AdminUserDetailPage() {
  return (
    <Suspense fallback={<p className="text-sm text-paper-muted">Loading…</p>}>
      <UserDetailBody />
    </Suspense>
  );
}

function UserDetailBody() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { confirmIfDirty } = useUnsavedGuard();
  const [user, setUser] = useState<UserDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [draft, setDraft] = useState<{
    buyer: Record<string, string>;
    seller: Record<string, string>;
    bank: Record<string, string>;
  }>({ buyer: {}, seller: {}, bank: {} });

  // Dirty = actively editing AND at least one field differs from the server
  // snapshot. We recompute the diff via buildPatch below; guard against user
  // being null so the effect can run pre-fetch without exploding.
  const hasChanges = useMemo(() => {
    if (!user) return false;
    const patch = buildPatch(user, draft);
    return !!(patch.buyer || patch.seller || patch.bank);
  }, [user, draft]);
  useDirtyFlag(editing && hasChanges);

  useEffect(() => {
    if (!params?.id) return;
    adminApi
      .user(params.id)
      .then((u) => {
        setUser(u);
        setDraft(buildDraft(u));
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Load failed"));
  }, [params?.id]);

  useEffect(() => {
    if (!savedAt) return;
    const t = window.setTimeout(() => setSavedAt(null), 3000);
    return () => window.clearTimeout(t);
  }, [savedAt]);

  const startEdit = () => {
    if (!user) return;
    setDraft(buildDraft(user));
    setErr(null);
    setEditing(true);
  };
  const cancelEdit = () => {
    if (hasChanges) {
      const ok = window.confirm(
        "Discard your changes?",
      );
      if (!ok) return;
    }
    if (user) setDraft(buildDraft(user));
    setErr(null);
    setEditing(false);
  };

  const handleChange =
    (section: "buyer" | "seller" | "bank", key: string) =>
    (e: ChangeEvent<HTMLInputElement>) => {
      setDraft((prev) => ({
        ...prev,
        [section]: { ...prev[section], [key]: e.target.value },
      }));
    };

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) return;
    setErr(null);
    setSaving(true);
    try {
      const patch = buildPatch(user, draft);
      if (!patch.buyer && !patch.seller && !patch.bank) {
        setEditing(false);
        setSaving(false);
        return;
      }
      const updated = await adminApi.updateUser(user.userId, patch);
      setUser(updated);
      setDraft(buildDraft(updated));
      setEditing(false);
      setSavedAt(Date.now());
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (err && !user) return <p className="text-sm text-danger">Could not load: {err}</p>;
  if (!user) return <p className="text-sm text-paper-muted">Loading…</p>;

  return (
    <form onSubmit={handleSave} className="space-y-6" noValidate>
      <Link
        href="/admin/users"
        onClick={(e) => {
          e.preventDefault();
          confirmIfDirty(() => router.push("/admin/users"));
        }}
        className="inline-flex items-center gap-1.5 text-xs text-paper-muted transition-colors hover:text-paper"
      >
        <ArrowLeft aria-hidden className="h-3.5 w-3.5" />
        Back to users
      </Link>

      {/* Header */}
      <header className="surface p-5 sm:p-6">
        <div className="flex flex-wrap items-start gap-4">
          <span className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-line-soft bg-ink-elevated text-lg font-semibold text-paper">
            {(user.buyer?.fullName || user.mobile || "?")
              .slice(0, 2)
              .toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] uppercase tracking-widest text-paper-muted">
              User · {user.userId.slice(0, 8)}
            </p>
            <h1 className="mt-1 truncate text-2xl font-semibold tracking-tight text-paper">
              {user.buyer?.fullName || user.mobile || "—"}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
              <RoleBadge type="buyer" active={user.hasBuyerData} />
              <RoleBadge type="seller" active={user.hasSellerData} />
              <span className="text-paper-muted">·</span>
              <StatusBadge status={user.status} />
              <span className="text-paper-muted">·</span>
              <span className="text-paper-muted">
                joined {formatDate(user.createdAt)}
              </span>
              {user.mobile ? (
                <>
                  <span className="text-paper-muted">·</span>
                  <span className="text-paper">+91 {user.mobile}</span>
                </>
              ) : null}
            </div>
          </div>

          {/* Edit / Save controls */}
          <div className="flex flex-wrap items-center gap-2">
            {savedAt ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-accent">
                <Check className="h-3.5 w-3.5" aria-hidden />
                Saved
              </span>
            ) : null}
            {editing ? (
              <>
                <button
                  type="button"
                  onClick={cancelEdit}
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 rounded-md border border-line-soft px-3 py-1.5 text-xs text-paper-muted transition-colors hover:text-paper"
                >
                  <X aria-hidden className="h-3.5 w-3.5" />
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="btn-primary inline-flex items-center gap-1.5 !py-1.5 !text-xs"
                >
                  <span className="inline-flex items-center gap-1.5">
                    <Save aria-hidden className="h-3.5 w-3.5" />
                    {saving ? "Saving…" : "Save changes"}
                  </span>
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={startEdit}
                className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-xs text-paper transition-colors hover:border-accent hover:bg-accent-soft"
              >
                <Pencil aria-hidden className="h-3.5 w-3.5" />
                Edit
              </button>
            )}
          </div>
        </div>

        {err && editing ? (
          <p className="mt-4 text-sm font-medium text-danger" role="alert">
            {err}
          </p>
        ) : null}
      </header>

      {/* Buyer identity + address side-by-side */}
      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard
          icon={<UserRound className="h-4 w-4" />}
          title="Buyer identity"
          span={2}
        >
          <FieldGrid
            fields={BUYER_IDENTITY}
            block={user.buyer}
            draft={draft.buyer}
            editing={editing}
            onChange={handleChange}
            section="buyer"
          />
        </SectionCard>

        <SectionCard
          icon={<MapPin className="h-4 w-4" />}
          title="Address"
        >
          <FieldGrid
            fields={BUYER_ADDRESS}
            block={user.buyer}
            draft={draft.buyer}
            editing={editing}
            onChange={handleChange}
            section="buyer"
            singleCol
          />
        </SectionCard>
      </div>

      <SectionCard title="Web presence">
        <FieldGrid
          fields={BUYER_WEB}
          block={user.buyer}
          draft={draft.buyer}
          editing={editing}
          onChange={handleChange}
          section="buyer"
          cols={3}
        />
      </SectionCard>

      {/* Seller + Bank */}
      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard
          icon={<Building2 className="h-4 w-4" />}
          title="Business identity"
          span={2}
        >
          <FieldGrid
            fields={SELLER_FIELDS}
            block={user.seller}
            draft={draft.seller}
            editing={editing}
            onChange={handleChange}
            section="seller"
          />
        </SectionCard>

        <SectionCard
          icon={<Landmark className="h-4 w-4" />}
          title="Bank account"
        >
          <FieldGrid
            fields={BANK_FIELDS}
            block={user.bank}
            draft={draft.bank}
            editing={editing}
            onChange={handleChange}
            section="bank"
            singleCol
          />
        </SectionCard>
      </div>
    </form>
  );
}

// ── Draft <-> data helpers ────────────────────────────────────────────────

function buildDraft(u: UserDetail) {
  const grab = (block: Record<string, string | null> | null | undefined) => {
    const out: Record<string, string> = {};
    if (!block) return out;
    for (const [k, v] of Object.entries(block)) {
      out[k] = v ?? "";
    }
    return out;
  };
  return {
    buyer: grab(u.buyer),
    seller: grab(u.seller),
    bank: grab(u.bank),
  };
}

function buildPatch(
  user: UserDetail,
  draft: ReturnType<typeof buildDraft>,
) {
  const diffSection = (
    original: Record<string, string | null> | null | undefined,
    next: Record<string, string>,
    fields: FieldSpec[],
  ): Record<string, string | null> | null => {
    const changes: Record<string, string | null> = {};
    for (const f of fields) {
      const before = (original?.[f.key] ?? "") as string;
      const after = (next[f.key] ?? "").trim();
      if (before.trim() === after) continue;
      changes[f.key] = after === "" ? null : after;
    }
    return Object.keys(changes).length ? changes : null;
  };
  const buyerFields = [...BUYER_IDENTITY, ...BUYER_ADDRESS, ...BUYER_WEB];
  const patch: {
    buyer?: Record<string, string | null>;
    seller?: Record<string, string | null>;
    bank?: Record<string, string | null>;
  } = {};
  const b = diffSection(user.buyer, draft.buyer, buyerFields);
  if (b) patch.buyer = b;
  const s = diffSection(user.seller, draft.seller, SELLER_FIELDS);
  if (s) patch.seller = s;
  const bk = diffSection(user.bank, draft.bank, BANK_FIELDS);
  if (bk) patch.bank = bk;
  return patch;
}

// ── UI bits ────────────────────────────────────────────────────────────────

function SectionCard({
  icon,
  title,
  children,
  span,
}: {
  icon?: React.ReactNode;
  title: string;
  children: React.ReactNode;
  span?: 2 | 3;
}) {
  return (
    <section
      className={cn(
        "surface p-5 sm:p-6",
        span === 2 && "lg:col-span-2",
        span === 3 && "lg:col-span-3",
      )}
    >
      <div className="flex items-center gap-2">
        {icon ? (
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-accent/10 text-accent">
            {icon}
          </span>
        ) : null}
        <p className="text-title text-paper">{title}</p>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function FieldGrid({
  fields,
  block,
  draft,
  editing,
  onChange,
  section,
  cols = 2,
  singleCol,
}: {
  fields: FieldSpec[];
  block: Record<string, string | null> | null | undefined;
  draft: Record<string, string>;
  editing: boolean;
  onChange: (
    section: "buyer" | "seller" | "bank",
    key: string,
  ) => (e: ChangeEvent<HTMLInputElement>) => void;
  section: "buyer" | "seller" | "bank";
  cols?: 2 | 3;
  singleCol?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid gap-x-4 gap-y-3",
        !singleCol && cols === 3 && "sm:grid-cols-3",
        !singleCol && cols === 2 && "sm:grid-cols-2",
      )}
    >
      {fields.map((f) => (
        <FieldCell
          key={f.key}
          spec={f}
          value={block?.[f.key] ?? null}
          draftValue={draft[f.key] ?? ""}
          editing={editing}
          onChange={onChange(section, f.key)}
          wide={f.wide}
        />
      ))}
    </div>
  );
}

function FieldCell({
  spec,
  value,
  draftValue,
  editing,
  onChange,
  wide,
}: {
  spec: FieldSpec;
  value: string | null;
  draftValue: string;
  editing: boolean;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  wide?: boolean;
}) {
  return (
    <div className={cn(wide && "sm:col-span-2")}>
      <p className="text-[10px] uppercase tracking-widest text-paper-muted">
        {spec.label}
      </p>
      {editing ? (
        <input
          className={cn("field mt-1", spec.mono && "font-mono")}
          value={draftValue}
          onChange={onChange}
          placeholder="—"
          spellCheck={false}
          autoComplete="off"
        />
      ) : (
        <p
          className={cn(
            "mt-1 text-sm text-paper",
            !value && "text-paper-muted/70",
            spec.mono && value && "font-mono",
          )}
        >
          {value ?? "—"}
        </p>
      )}
    </div>
  );
}

function RoleBadge({ type, active }: { type: "buyer" | "seller"; active: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-widest",
        active
          ? "border-line bg-ink-elevated text-paper"
          : "border-line-soft bg-transparent text-paper-muted/60",
      )}
      style={
        active
          ? {
              color: type === "seller" ? "var(--violet)" : "var(--accent)",
            }
          : undefined
      }
    >
      {type}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const verified = status === "verified";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-widest",
        verified
          ? "border-accent/30 bg-accent-soft text-paper"
          : "border-line-soft bg-ink-elevated text-paper-muted",
      )}
    >
      {verified ? (
        <ShieldCheck aria-hidden className="h-3 w-3 text-accent" />
      ) : null}
      {status}
    </span>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
