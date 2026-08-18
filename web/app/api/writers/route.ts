import { NextRequest, NextResponse } from "next/server";

import { requireActiveMember } from "@/lib/auth";
import { assertSameOrigin, HttpError, jsonError, readJsonObject } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_LABEL = 120;

/**
 * The writer registry maps an opaque identifier to a readable label.
 *
 * Labels name real clinicians, so they are served only to signed-in members
 * for selection in the workbench and never leave through gold export, which
 * carries the opaque identifier alone.
 */
export async function GET() {
  try {
    await requireActiveMember();
    const admin = createAdminClient();
    const { data, error } = await admin
      .from("writers")
      .select("writer_group_id,display_label")
      .eq("active", true)
      .order("display_label", { ascending: true })
      .limit(500);
    if (error) throw error;
    return NextResponse.json({
      writers: (data ?? []).map((row) => ({
        id: String(row.writer_group_id),
        label: String(row.display_label),
      })),
    });
  } catch (error) {
    return jsonError(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    assertSameOrigin(request);
    const member = await requireActiveMember();
    const body = await readJsonObject(request);
    const label = typeof body.label === "string" ? body.label.trim() : "";
    if (!label || label.length > MAX_LABEL) {
      throw new HttpError(400, "invalid_writer", `Enter a writer label of 1 to ${MAX_LABEL} characters.`);
    }
    const admin = createAdminClient();
    const { data, error } = await admin.rpc("dcal_create_writer", {
      p_actor_user_id: member.id,
      p_display_label: label,
    });
    if (error) throw error;
    const result = Array.isArray(data) ? data[0] : data;
    const created = Boolean((result as { created?: unknown } | null)?.created);
    return NextResponse.json(
      {
        id: String((result as { writer_group_id?: unknown }).writer_group_id),
        label: String((result as { display_label?: unknown }).display_label),
        created,
      },
      { status: created ? 201 : 200 },
    );
  } catch (error) {
    return jsonError(error);
  }
}
