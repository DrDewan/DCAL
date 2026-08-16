import { redirect } from "next/navigation";

import { currentMember } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function PendingPage() {
  const member = await currentMember();
  if (!member) redirect("/login");
  if (member.active) redirect("/");
  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="pending-title">
        <div className="auth-brand"><span className="dialog-mark">DC</span><span>DCAL</span></div>
        <p className="eyebrow">Account pending</p>
        <h1 id="pending-title">An administrator must activate this account.</h1>
        <p>Your sign-in worked, but this account cannot view or annotate documents yet.</p>
        <form action="/auth/signout" method="post">
          <button className="secondary-button auth-submit" type="submit">Sign out</button>
        </form>
      </section>
    </main>
  );
}
