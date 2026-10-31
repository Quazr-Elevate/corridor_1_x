"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ADMIN_ROLE_LABEL,
  adminApi,
  errorMessage,
  type AdminAccount,
  type AdminRole,
  type AdminWithPassword,
} from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { LaneHeader } from "@/components/admin/tower";
import { fmtAgo } from "@/components/admin/format";
import { useTower } from "@/components/shell/TowerShell";

const ROLE_OPTIONS = [
  { value: "reviewer", label: "Reviewer — reviews businesses and documents" },
  { value: "super_admin", label: "Super admin — everything, incl. countries and admins" },
];

/**
 * Admins (super admin only) — named accounts with a role. New accounts and
 * password resets get a temporary password shown once here; the person sets
 * their own at first sign-in. Lockouts after repeated wrong passwords are
 * cleared here too.
 */
export default function AdminsPage() {
  const { me, can } = useTower();
  const toast = useToast();
  const [rows, setRows] = useState<AdminAccount[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [issued, setIssued] = useState<AdminWithPassword | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await adminApi.admins());
      setErr(null);
    } catch (e) {
      setErr(errorMessage(e, "Couldn't load admins."));
    }
  }, []);

  useEffect(() => {
    if (can("admins.manage")) void load();
  }, [can, load]);

  if (!can("admins.manage")) {
    return (
      <div className="pt-4">
        <Notice tone="frozen" title="Super admins only">Your role doesn’t include managing admin accounts.</Notice>
      </div>
    );
  }

  async function act(id: string, run: () => Promise<unknown>, done: string) {
    setBusyId(id);
    try {
      await run();
      toast(done, "verified");
      await load();
    } catch (e) {
      toast(errorMessage(e, "That didn't work."), "frozen");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="pt-4">
      <LaneHeader
        eyebrow="Lane · Access"
        title="Admins"
        subtitle="Who can open the tower, and what their role allows. One device per admin; sessions end after 30 minutes idle."
        actions={
          <Button icon="plus" onClick={() => setAdding(true)}>
            Add admin
          </Button>
        }
      />

      {err ? (
        <div className="mt-6">
          <Notice tone="frozen" title="Couldn't load admins">
            {err}
          </Notice>
        </div>
      ) : null}

      <div className="mt-6">
        {!rows && !err ? (
          <div className="relief rounded-[28px] p-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="mt-2 h-14 rounded-[14px] first:mt-0" />
            ))}
          </div>
        ) : rows && rows.length === 0 ? (
          <Card className="rounded-[28px] p-2">
            <EmptyState icon="users" title="No admins yet">Add the first reviewer.</EmptyState>
          </Card>
        ) : rows ? (
          <ul className="relief divide-y divide-line overflow-hidden rounded-[28px]">
            {rows.map((a) => {
              const self = a.id === me?.id;
              const busy = busyId === a.id;
              return (
                <li key={a.id} className="flex flex-col gap-4 px-5 py-4 sm:px-6 lg:flex-row lg:items-center">
                  <div className="min-w-0 flex-1">
                    <p className="t-body flex flex-wrap items-center gap-2 font-medium text-fg">
                      <span className="truncate">{a.fullName}</span>
                      {self ? <Chip tone="quiet" size="sm" noIcon>You</Chip> : null}
                      <Chip tone={a.role === "super_admin" ? "solid" : "neutral"} size="sm" noIcon>
                        {ADMIN_ROLE_LABEL[a.role]}
                      </Chip>
                      {a.status === "disabled" ? <Chip tone="frozen" size="sm">Disabled</Chip> : null}
                      {a.lockState !== "none" ? (
                        <Chip tone="frozen" size="sm" icon="lock">
                          {a.lockState === "support" ? "Locked · needs unlock" : "Locked"}
                        </Chip>
                      ) : null}
                      {a.mustChangePassword ? <Chip tone="move" size="sm" icon="key">Temporary password</Chip> : null}
                    </p>
                    <p className="t-sub mt-1 truncate text-fg-3">
                      {a.email} · {a.lastLoginAt ? `last sign-in ${fmtAgo(a.lastLoginAt)}` : "never signed in"} · added by{" "}
                      {a.createdBy}
                    </p>
                  </div>
                  {self ? null : (
                    <div className={cn("flex flex-wrap gap-2", busy && "pointer-events-none opacity-60")}>
                      {a.lockState !== "none" ? (
                        <Button size="sm" variant="secondary" icon="unlock"
                          onClick={() => act(a.id, () => adminApi.unlockAdmin(a.id), `${a.fullName} unlocked`)}>
                          Unlock
                        </Button>
                      ) : null}
                      <Button size="sm" variant="secondary"
                        onClick={() => act(a.id, () => adminApi.updateAdmin(a.id, {
                          role: a.role === "super_admin" ? "reviewer" : "super_admin",
                        }), "Role updated")}>
                        Make {a.role === "super_admin" ? "reviewer" : "super admin"}
                      </Button>
                      <Button size="sm" variant="secondary" icon="key"
                        onClick={async () => {
                          setBusyId(a.id);
                          try {
                            setIssued(await adminApi.resetAdminPassword(a.id));
                            await load();
                          } catch (e) {
                            toast(errorMessage(e, "Couldn't reset the password."), "frozen");
                          } finally {
                            setBusyId(null);
                          }
                        }}>
                        Reset password
                      </Button>
                      <Button size="sm" variant="secondary" icon="logout"
                        onClick={() => act(a.id, () => adminApi.signOutAdmin(a.id), `${a.fullName} signed out`)}>
                        Sign out
                      </Button>
                      <Button size="sm" variant={a.status === "active" ? "danger" : "secondary"}
                        onClick={() => act(a.id, () => adminApi.updateAdmin(a.id, {
                          status: a.status === "active" ? "disabled" : "active",
                        }), a.status === "active" ? `${a.fullName} disabled` : `${a.fullName} enabled`)}>
                        {a.status === "active" ? "Disable" : "Enable"}
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>

      <AddAdminSheet
        open={adding}
        onClose={() => setAdding(false)}
        onCreated={async (r) => {
          setAdding(false);
          setIssued(r);
          await load();
        }}
      />
      <TemporaryPasswordSheet issued={issued} onClose={() => setIssued(null)} />
    </div>
  );
}

function AddAdminSheet({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (r: AdminWithPassword) => void;
}) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<AdminRole>("reviewer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setEmail("");
      setFullName("");
      setRole("reviewer");
      setError(null);
    }
  }, [open]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(await adminApi.createAdmin({ email: email.trim().toLowerCase(), fullName: fullName.trim(), role }));
    } catch (err) {
      setError(errorMessage(err, "Couldn't add the admin."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Add admin"
      description="They’ll get a temporary password from you, and choose their own at first sign-in."
      footer={
        <Button type="submit" form="add-admin" loading={busy} block>
          Create account
        </Button>
      }
    >
      <form id="add-admin" onSubmit={submit} className="space-y-5">
        <Input label="Work email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Input label="Full name" required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <Select label="Role" value={role} onChange={(e) => setRole(e.target.value as AdminRole)} options={ROLE_OPTIONS} />
        {error ? <Notice tone="frozen">{error}</Notice> : null}
      </form>
    </Sheet>
  );
}

function TemporaryPasswordSheet({ issued, onClose }: { issued: AdminWithPassword | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => setCopied(false), [issued]);
  return (
    <Sheet
      open={!!issued}
      onClose={onClose}
      title="Temporary password"
      description="Shown only once. Share it privately — a call or chat, not an email to the same inbox."
      footer={
        <Button onClick={onClose} block>
          Done
        </Button>
      }
    >
      {issued ? (
        <div className="space-y-4">
          <p className="t-sub text-fg-2">
            {issued.admin.fullName} · {issued.admin.email}
          </p>
          <div className="well flex items-center justify-between gap-3 rounded-[18px] px-4 py-3">
            <code className="t-code select-all break-all text-fg">{issued.temporaryPassword}</code>
            <Button
              size="sm"
              variant="secondary"
              icon={copied ? "check" : "copy"}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(issued.temporaryPassword);
                  setCopied(true);
                } catch {
                  /* clipboard blocked — the text is selectable */
                }
              }}
            >
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <p className="t-sub flex items-start gap-2 text-fg-3">
            <Icon name="lock" size={14} className="mt-0.5 shrink-0" />
            It works once: they must set a new password (12+ characters) before they can do anything else.
          </p>
        </div>
      ) : null}
    </Sheet>
  );
}
