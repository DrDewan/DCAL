import { timingSafeEqual } from "node:crypto";

import { createAdminClient, createSessionClient } from "@/lib/supabase/server";
import { ingestionToken } from "@/lib/env";
import { HttpError } from "@/lib/http";

export type MemberRole = "annotator" | "reviewer" | "admin";

export type Member = {
  id: string;
  email: string;
  displayName: string;
  role: MemberRole;
  active: boolean;
};

export async function currentMember(): Promise<Member | null> {
  const session = await createSessionClient();
  const { data, error } = await session.auth.getUser();
  if (error || !data.user) return null;
  const admin = createAdminClient();
  const profile = await admin
    .from("profiles")
    .select("id,display_name,role,active")
    .eq("id", data.user.id)
    .maybeSingle();
  if (profile.error) throw profile.error;
  if (!profile.data) return null;
  return {
    id: data.user.id,
    email: data.user.email || "",
    displayName: profile.data.display_name,
    role: profile.data.role as MemberRole,
    active: Boolean(profile.data.active),
  };
}

export async function requireActiveMember() {
  const member = await currentMember();
  if (!member) throw new HttpError(401, "unauthorized", "Sign in is required.");
  if (!member.active) {
    throw new HttpError(403, "membership_inactive", "Your DCAL account is awaiting activation.");
  }
  return member;
}

export async function requireExportMember() {
  const member = await requireActiveMember();
  if (!(["reviewer", "admin"] as MemberRole[]).includes(member.role)) {
    throw new HttpError(403, "forbidden", "Reviewer or administrator access is required.");
  }
  return member;
}

export function requireIngestionBearer(authorization: string | null) {
  const supplied = authorization?.startsWith("Bearer ")
    ? authorization.slice("Bearer ".length)
    : "";
  const expected = ingestionToken();
  const suppliedBytes = Buffer.from(supplied);
  const expectedBytes = Buffer.from(expected);
  if (
    suppliedBytes.length !== expectedBytes.length ||
    !timingSafeEqual(suppliedBytes, expectedBytes)
  ) {
    throw new HttpError(401, "unauthorized", "Ingestion token required.");
  }
}
