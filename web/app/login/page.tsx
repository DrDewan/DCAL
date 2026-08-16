import { redirect } from "next/navigation";

import { currentMember } from "@/lib/auth";

import { LoginForm } from "./login-form";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const member = await currentMember();
  if (member?.active) redirect("/");
  if (member) redirect("/pending");
  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="login-title">
        <div className="auth-brand"><span className="dialog-mark">DC</span><span>DCAL</span></div>
        <p className="eyebrow">Private workspace</p>
        <h1 id="login-title">Annotation workbench</h1>
        <p>Sign in with the account issued by the DCAL administrator. Patient documents are never public.</p>
        <LoginForm />
      </section>
    </main>
  );
}
