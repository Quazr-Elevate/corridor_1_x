import { redirect } from "next/navigation";

/**
 * The Docs lane merged into the single business review (/admin/verify):
 * profile and documents are reviewed and decided together there.
 */
export default function DocsLaneRedirect() {
  redirect("/admin/verify");
}
