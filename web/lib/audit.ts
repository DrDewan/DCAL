import { createAdminClient } from "@/lib/supabase/server";

type PageAccess =
  | { action: "view_image"; taskId: number }
  | { action: "export_gold"; recordCount: number };

/**
 * Records a clinical page read or a gold export.
 *
 * Auditing is deliberately limited to the two routes that actually hand over
 * patient content: page image bytes and the gold export. Auditing every queue
 * or task-metadata request would bury real access events in navigation noise.
 *
 * A failure to record must not fail the request the user is performing, but it
 * must be visible, so it is logged without page or patient detail.
 */
export async function recordPageAccess(actorUserId: string, event: PageAccess) {
  try {
    const admin = createAdminClient();
    const { error } = await admin.rpc("dcal_record_page_access", {
      p_actor_user_id: actorUserId,
      p_action: event.action,
      p_task_id: event.action === "view_image" ? event.taskId : null,
      p_record_count: event.action === "export_gold" ? event.recordCount : null,
    });
    if (error) throw error;
  } catch {
    console.error("DCAL page access audit failed", { action: event.action });
  }
}
