import { NextResponse } from "next/server";

import { requireActiveMember } from "@/lib/auth";
import { taxonomyPayload } from "@/lib/contracts";
import { jsonError } from "@/lib/http";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    await requireActiveMember();
    return NextResponse.json(taxonomyPayload);
  } catch (error) {
    return jsonError(error);
  }
}
