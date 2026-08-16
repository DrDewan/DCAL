import { NextRequest, NextResponse } from "next/server";

import { assertSameOrigin } from "@/lib/http";
import { createSessionClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  assertSameOrigin(request);
  const supabase = await createSessionClient();
  await supabase.auth.signOut();
  return NextResponse.redirect(new URL("/login", request.url), 303);
}
