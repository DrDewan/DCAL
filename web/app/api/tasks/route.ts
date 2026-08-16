import { NextRequest, NextResponse } from "next/server";

import { requireActiveMember } from "@/lib/auth";
import { TASK_STATUSES, taxonomySets } from "@/lib/contracts";
import { HttpError, jsonError } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";
import { type TaskRow, taskColumns, taskSummary } from "@/lib/tasks";

export const dynamic = "force-dynamic";

async function countTasks(status?: string, eligible = false) {
  const admin = createAdminClient();
  let query = admin.from("tasks").select("id", { count: "exact", head: true });
  if (status) query = query.eq("status", status);
  if (eligible) query = query.eq("dataset_eligible", true);
  const { count, error } = await query;
  if (error) throw error;
  return count ?? 0;
}

export async function GET(request: NextRequest) {
  try {
    await requireActiveMember();
    const status = request.nextUrl.searchParams.get("status")?.trim() || "";
    const documentType = request.nextUrl.searchParams.get("document_type")?.trim() || "";
    const search = request.nextUrl.searchParams.get("q")?.trim() || "";
    if (status && !(TASK_STATUSES as readonly string[]).includes(status)) {
      throw new HttpError(400, "invalid_filter", "Unknown status filter.");
    }
    if (documentType && !taxonomySets.documentTypes.has(documentType)) {
      throw new HttpError(400, "invalid_filter", "Unknown document type filter.");
    }
    if (search.length > 100) throw new HttpError(400, "invalid_filter", "Search is too long.");

    const admin = createAdminClient();
    let query = admin
      .from("tasks")
      .select(taskColumns)
      .order("updated_at", { ascending: false })
      .order("id", { ascending: false })
      .limit(250);
    if (status) query = query.eq("status", status);
    if (documentType) query = query.eq("annotation->>document_type", documentType);
    if (search) {
      const idMatch = /^page_([0-9]{6,})$/i.exec(search);
      if (idMatch) query = query.eq("id", Number(idMatch[1]));
      else query = query.ilike("assigned_to_name", `%${search.replaceAll("%", "\\%").replaceAll("_", "\\_")}%`);
    }
    const [{ data, error }, counts, total, datasetEligible] = await Promise.all([
      query,
      Promise.all(TASK_STATUSES.map((item) => countTasks(item))),
      countTasks(),
      countTasks(undefined, true),
    ]);
    if (error) throw error;
    return NextResponse.json({
      tasks: ((data ?? []) as unknown as TaskRow[]).map(taskSummary),
      counts: Object.fromEntries(TASK_STATUSES.map((item, index) => [item, counts[index]])),
      total,
      dataset_eligible: datasetEligible,
    });
  } catch (error) {
    return jsonError(error);
  }
}
