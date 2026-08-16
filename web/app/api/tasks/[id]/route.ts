import { NextRequest, NextResponse } from "next/server";

import { requireActiveMember } from "@/lib/auth";
import { TASK_STATUSES } from "@/lib/contracts";
import { assertSameOrigin, HttpError, jsonError, readJsonObject } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";
import { parseTaskId, type TaskRow, taskColumns, taskDetail } from "@/lib/tasks";
import { validateAnnotation } from "@/lib/validation";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Context = { params: Promise<{ id: string }> };

async function getTask(id: number) {
  const admin = createAdminClient();
  const { data, error } = await admin.from("tasks").select(taskColumns).eq("id", id).maybeSingle();
  if (error) throw error;
  if (!data) throw new HttpError(404, "task_not_found", "Task not found.");
  return data as unknown as TaskRow;
}

export async function GET(_request: NextRequest, context: Context) {
  try {
    await requireActiveMember();
    const { id: publicId } = await context.params;
    return NextResponse.json(taskDetail(await getTask(parseTaskId(publicId))));
  } catch (error) {
    return jsonError(error);
  }
}

export async function PUT(request: NextRequest, context: Context) {
  try {
    assertSameOrigin(request);
    const member = await requireActiveMember();
    const { id: publicId } = await context.params;
    const taskId = parseTaskId(publicId);
    const body = await readJsonObject(request);
    const expectedVersion = body.expected_version;
    if (!Number.isInteger(expectedVersion) || (expectedVersion as number) < 1) {
      throw new HttpError(400, "invalid_request", "expected_version must be a positive integer.");
    }
    const status = body.status === null || body.status === undefined ? null : body.status;
    if (status !== null && (typeof status !== "string" || !(TASK_STATUSES as readonly string[]).includes(status))) {
      throw new HttpError(400, "invalid_request", "Unknown task status.");
    }
    const annotation = validateAnnotation(body.annotation, status === "completed");
    const admin = createAdminClient();
    const { error } = await admin.rpc("dcal_save_task", {
      p_actor_user_id: member.id,
      p_task_id: taskId,
      p_expected_version: expectedVersion as number,
      p_annotation: annotation,
      p_status: status,
    });
    if (error) {
      if (error.code === "40001") {
        throw new HttpError(409, "version_conflict", "This page changed elsewhere. Reload before saving.");
      }
      if (error.code === "P0002") throw new HttpError(404, "task_not_found", "Task not found.");
      throw error;
    }
    return NextResponse.json(taskDetail(await getTask(taskId)));
  } catch (error) {
    return jsonError(error);
  }
}
