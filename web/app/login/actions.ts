"use server";

import { redirect } from "next/navigation";

import { createSessionClient } from "@/lib/supabase/server";

export type LoginState = { error: string | null };

export async function loginAction(_state: LoginState, formData: FormData): Promise<LoginState> {
  const email = formData.get("email");
  const password = formData.get("password");
  if (typeof email !== "string" || typeof password !== "string" || !email || !password) {
    return { error: "Enter your email address and password." };
  }
  const supabase = await createSessionClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { error: "The email address or password is incorrect." };
  redirect("/");
}
