import { NextRequest, NextResponse } from "next/server";

import { requireIngestionBearer } from "@/lib/auth";
import { blankAnnotation, INGESTION_SCHEMA, PAGE_BUCKET } from "@/lib/contracts";
import { validateIngestionTask } from "@/lib/ingestion";
import { HttpError, jsonError, readJsonObject } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  try {
    requireIngestionBearer(request.headers.get("authorization"));
    const admin = createAdminClient();
    const index: Record<string, number> = {};
    for (let start = 0; ; start += 1000) {
      const { data, error } = await admin
        .from("tasks")
        .select("id,ingestion_key")
        .order("id", { ascending: true })
        .range(start, start + 999);
      if (error) throw error;
      for (const row of data ?? []) index[String(row.ingestion_key)] = Number(row.id);
      if (!data || data.length < 1000) break;
    }
    return NextResponse.json({ tasks: index });
  } catch (error) {
    return jsonError(error);
  }
}

async function assertStored(path: string) {
  const admin = createAdminClient();
  const segments = path.split("/");
  const fileName = segments.pop()!;
  const { data, error } = await admin.storage.from(PAGE_BUCKET).list(segments.join("/"), {
    limit: 2,
    search: fileName,
  });
  if (error) throw error;
  if (!data.some((item) => item.name === fileName)) {
    throw new HttpError(400, "missing_page", "The rendered page must be uploaded before task creation.");
  }
}

export async function POST(request: NextRequest) {
  try {
    requireIngestionBearer(request.headers.get("authorization"));
    const task = validateIngestionTask(await readJsonObject(request));
    await assertStored(task.storagePath);
    const admin = createAdminClient();
    const directMatch = await admin
      .from("tasks")
      .select("id")
      .or(`ingestion_key.eq.${task.ingestionKey},source_sha256.eq.${task.sourceSha256}`)
      .limit(1)
      .maybeSingle();
    if (directMatch.error) throw directMatch.error;
    let existing = directMatch.data;
    if (!existing) {
      const rawMatch = await admin
        .from("tasks")
        .select("id")
        .eq("source_origin", "manual_upload")
        .eq("raw_source_sha256", task.rawSourceSha256)
        .limit(1)
        .maybeSingle();
      if (rawMatch.error) throw rawMatch.error;
      existing = rawMatch.data;
    }
    const provenance = {
      ingestion_key: task.ingestionKey,
      source_origin: "google_drive",
      dataset_eligible: true,
      source_object_id: task.sourceObjectId,
      source_sha256: task.sourceSha256,
      raw_source_sha256: task.rawSourceSha256,
      patient_group_id: task.patientGroupId,
      encounter_group_id: task.encounterGroupId,
      writer_group_ids: task.writerGroupIds,
      source_page_index: task.sourcePageIndex,
      ingestion_schema_version: INGESTION_SCHEMA,
      render_profile: task.renderProfile,
      storage_bucket: PAGE_BUCKET,
      storage_path: task.storagePath,
      image_width: task.imageWidth,
      image_height: task.imageHeight,
      updated_at: new Date().toISOString(),
    };
    if (existing) {
      const { error } = await admin.from("tasks").update(provenance).eq("id", existing.id);
      if (error) throw error;
      return NextResponse.json({ id: Number(existing.id), created: false });
    }
    const inserted = await admin
      .from("tasks")
      .insert({ ...provenance, annotation: blankAnnotation() })
      .select("id")
      .single();
    if (inserted.error) {
      if (inserted.error.code === "23505") {
        const raced = await admin
          .from("tasks")
          .select("id")
          .eq("source_sha256", task.sourceSha256)
          .single();
        if (raced.error) throw raced.error;
        return NextResponse.json({ id: Number(raced.data.id), created: false });
      }
      throw inserted.error;
    }
    return NextResponse.json({ id: Number(inserted.data.id), created: true }, { status: 201 });
  } catch (error) {
    return jsonError(error);
  }
}
