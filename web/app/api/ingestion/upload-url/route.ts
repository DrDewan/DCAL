import { NextRequest, NextResponse } from "next/server";

import { requireIngestionBearer } from "@/lib/auth";
import { canonicalPagePath } from "@/lib/ingestion";
import { HttpError, jsonError, readJsonObject } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    requireIngestionBearer(request.headers.get("authorization"));
    const body = await readJsonObject(request);
    if (body.mime_type !== "image/png") {
      throw new HttpError(415, "unsupported_media_type", "Ingestion pages must be PNG images.");
    }
    if (!Number.isInteger(body.size_bytes) || (body.size_bytes as number) < 1 || (body.size_bytes as number) > 25 * 1024 * 1024) {
      throw new HttpError(400, "invalid_upload", "Ingestion page size is invalid.");
    }
    const path = canonicalPagePath(String(body.source_sha256 ?? ""));
    const admin = createAdminClient();
    const { data, error } = await admin.storage
      .from("dcal-pages")
      .createSignedUploadUrl(path, { upsert: true });
    if (error || !data) throw error || new Error("Signed upload failed");
    return NextResponse.json({
      storage_path: path,
      signed_url: data.signedUrl,
    });
  } catch (error) {
    return jsonError(error);
  }
}
