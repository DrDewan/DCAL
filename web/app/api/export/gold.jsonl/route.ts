import { requireExportMember } from "@/lib/auth";
import { jsonError } from "@/lib/http";
import { createAdminClient } from "@/lib/supabase/server";
import { goldRecord, stableJson, type TaskRow, taskColumns } from "@/lib/tasks";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PAGE_SIZE = 500;

export async function GET() {
  try {
    await requireExportMember();
    const admin = createAdminClient();
    const lines: string[] = [];
    let skippedInvalid = 0;
    // Ordered by canonical page checksum so two exports of unchanged state
    // produce byte-identical output.
    for (let start = 0; ; start += PAGE_SIZE) {
      const { data, error } = await admin
        .from("tasks")
        .select(taskColumns)
        .eq("status", "completed")
        .eq("dataset_eligible", true)
        .order("source_sha256", { ascending: true })
        .range(start, start + PAGE_SIZE - 1);
      if (error) throw error;
      const rows = (data ?? []) as unknown as TaskRow[];
      for (const row of rows) {
        try {
          lines.push(stableJson(goldRecord(row)));
        } catch {
          // A row that no longer satisfies the completion contract must not
          // block the whole export. It is counted and reported instead.
          skippedInvalid += 1;
        }
      }
      if (rows.length < PAGE_SIZE) break;
    }
    return new Response(lines.length ? `${lines.join("\n")}\n` : "", {
      headers: {
        "Content-Type": "application/x-ndjson; charset=utf-8",
        "Content-Disposition": "attachment; filename=dcal-gold.jsonl",
        "Cache-Control": "private, no-store, max-age=0",
        "X-Content-Type-Options": "nosniff",
        "X-DCAL-Exported": String(lines.length),
        "X-DCAL-Skipped-Invalid": String(skippedInvalid),
      },
    });
  } catch (error) {
    return jsonError(error);
  }
}
