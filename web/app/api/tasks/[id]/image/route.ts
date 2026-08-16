import { NextRequest } from "next/server";

import { requireActiveMember } from "@/lib/auth";
import { jsonError, HttpError } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";
import { assertPrivatePage, parseTaskId, type TaskRow } from "@/lib/tasks";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Context = { params: Promise<{ id: string }> };

export async function GET(_request: NextRequest, context: Context) {
  try {
    await requireActiveMember();
    const { id: publicId } = await context.params;
    const taskId = parseTaskId(publicId);
    const admin = createAdminClient();
    const task = await admin
      .from("tasks")
      .select("storage_bucket,storage_path")
      .eq("id", taskId)
      .maybeSingle();
    if (task.error) throw task.error;
    if (!task.data) throw new HttpError(404, "task_not_found", "Task not found.");
    const row = task.data as unknown as Pick<TaskRow, "storage_bucket" | "storage_path">;
    assertPrivatePage(row);
    const result = await admin.storage.from(row.storage_bucket).download(row.storage_path);
    if (result.error || !result.data) {
      throw new HttpError(404, "image_unavailable", "Page image is unavailable.");
    }
    return new Response(await result.data.arrayBuffer(), {
      headers: {
        "Content-Type": result.data.type || "image/png",
        "Cache-Control": "private, no-store, max-age=0",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    return jsonError(error);
  }
}
