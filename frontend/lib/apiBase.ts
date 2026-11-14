/**
 * The backend serves every route under a version prefix (`/v1`). The
 * configured base (`NEXT_PUBLIC_API_BASE_URL`, `API_PROXY_TARGET` or the
 * same-origin `/api` proxy) names the host only; the version is added here
 * so a deployment's environment does not change when the prefix does.
 */
export const API_VERSION = "v1";

export function versioned(base: string): string {
  return `${base.replace(/\/+$/, "")}/${API_VERSION}`;
}
