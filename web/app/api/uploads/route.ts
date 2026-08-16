import { createHash } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";
import sharp from "sharp";

import { requireActiveMember } from "@/lib/auth";
import { assertSameOrigin, HttpError, jsonError } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";
import { publicTaskId } from "@/lib/tasks";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 30;

const MAX_REQUEST_BYTES = 4 * 1024 * 1024 + 256 * 1024;
const MAX_INPUT_BYTES = 4 * 1024 * 1024;
const MAX_OUTPUT_BYTES = 25 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function sha256(content: Buffer) {
  return createHash("sha256").update(content).digest("hex");
}

export async function POST(request: NextRequest) {
  try {
    assertSameOrigin(request);
    const member = await requireActiveMember();
    const declaredLength = Number(request.headers.get("content-length") || "0");
    if (declaredLength && declaredLength > MAX_REQUEST_BYTES) {
      throw new HttpError(413, "upload_too_large", "Upload one image smaller than 4 MiB at a time.");
    }
    const form = await request.formData();
    const files = form.getAll("files");
    if (files.length !== 1 || !(files[0] instanceof File)) {
      throw new HttpError(400, "invalid_upload", "Upload exactly one page image per request.");
    }
    const file = files[0];
    if (!ACCEPTED_TYPES.has(file.type)) {
      throw new HttpError(415, "unsupported_media_type", "Use a JPEG, PNG, or WebP page image.");
    }
    if (file.size < 1 || file.size > MAX_INPUT_BYTES) {
      throw new HttpError(413, "upload_too_large", "Upload one image smaller than 4 MiB at a time.");
    }
    const raw = Buffer.from(await file.arrayBuffer());
    const rawSha256 = sha256(raw);
    let normalized: Buffer;
    let width: number;
    let height: number;
    try {
      const output = await sharp(raw, { failOn: "warning", limitInputPixels: 40_000_000 })
        .rotate()
        .resize({ width: 3200, height: 3200, fit: "inside", withoutEnlargement: true })
        .png({ compressionLevel: 9 })
        .toBuffer({ resolveWithObject: true });
      normalized = output.data;
      width = output.info.width;
      height = output.info.height;
    } catch {
      throw new HttpError(400, "invalid_image", "The uploaded file is not a valid page image.");
    }
    if (normalized.length > MAX_OUTPUT_BYTES) {
      throw new HttpError(413, "upload_too_large", "The normalized page image exceeds 25 MiB.");
    }
    const sourceSha256 = sha256(normalized);
    const admin = createAdminClient();
    const existing = await admin
      .from("tasks")
      .select("id,dataset_eligible")
      .eq("source_sha256", sourceSha256)
      .maybeSingle();
    if (existing.error) throw existing.error;
    if (existing.data) {
      return NextResponse.json(
        {
          tasks: [{
            id: publicTaskId(Number(existing.data.id)),
            created: false,
            dataset_eligible: Boolean(existing.data.dataset_eligible),
          }],
        },
        { status: 200 },
      );
    }

    const storagePath = `pilot/${member.id}/${sourceSha256}.png`;
    const upload = await admin.storage.from("dcal-pages").upload(storagePath, normalized, {
      contentType: "image/png",
      cacheControl: "0",
      upsert: false,
    });
    if (upload.error) {
      const folder = `pilot/${member.id}`;
      const listed = await admin.storage.from("dcal-pages").list(folder, {
        limit: 2,
        search: `${sourceSha256}.png`,
      });
      if (listed.error || !listed.data.some((item) => item.name === `${sourceSha256}.png`)) {
        throw upload.error;
      }
    }
    const created = await admin.rpc("dcal_create_manual_task", {
      p_actor_user_id: member.id,
      p_source_sha256: sourceSha256,
      p_raw_source_sha256: rawSha256,
      p_storage_path: storagePath,
      p_image_width: width,
      p_image_height: height,
    });
    if (created.error) throw created.error;
    const result = Array.isArray(created.data) ? created.data[0] : created.data;
    const taskId = Number((result as { task_id?: unknown } | null)?.task_id);
    if (!Number.isSafeInteger(taskId) || taskId < 1) throw new Error("Invalid task result");
    return NextResponse.json(
      {
        tasks: [{
          id: publicTaskId(taskId),
          created: Boolean((result as { created?: unknown }).created),
          dataset_eligible: Boolean((result as { dataset_eligible?: unknown }).dataset_eligible),
        }],
      },
      { status: 201 },
    );
  } catch (error) {
    return jsonError(error);
  }
}
