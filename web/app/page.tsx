import Script from "next/script";
import { redirect } from "next/navigation";

import { currentMember } from "@/lib/auth";
import { workbenchMarkup } from "@/lib/workbench-markup";

export const dynamic = "force-dynamic";

export default async function WorkbenchPage() {
  const member = await currentMember();
  if (!member) redirect("/login");
  if (!member.active) redirect("/pending");
  const canExport = member.role === "reviewer" || member.role === "admin";
  return (
    <>
      <div dangerouslySetInnerHTML={{ __html: workbenchMarkup(canExport) }} />
      <Script src="/app.js" strategy="afterInteractive" />
    </>
  );
}
