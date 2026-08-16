import { NextResponse } from "next/server";

import { requireActiveMember } from "@/lib/auth";
import { jsonError } from "@/lib/http";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const member = await requireActiveMember();
    return NextResponse.json({
      id: member.id,
      email: member.email,
      display_name: member.displayName,
      role: member.role,
    });
  } catch (error) {
    return jsonError(error);
  }
}
