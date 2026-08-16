-- Keep database completion rules aligned with the repository taxonomy.
-- Financial/billing documents are clinical records and require regions.

create or replace function public.dcal_save_task(
  p_actor_user_id uuid,
  p_task_id bigint,
  p_expected_version integer,
  p_annotation jsonb,
  p_status text default null
)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := p_actor_user_id;
  v_actor_name text;
  v_current_version integer;
  v_current_status text;
  v_next_status text;
  v_completed_at timestamptz;
begin
  select display_name
  into v_actor_name
  from public.profiles
  where id = v_user_id and active = true;
  if v_actor_name is null then
    raise exception 'active DCAL membership required' using errcode = '42501';
  end if;
  if p_expected_version is null or p_expected_version < 1 then
    raise exception 'expected version must be positive' using errcode = '22023';
  end if;
  if p_status is not null
     and p_status not in ('unassigned', 'in_progress', 'completed', 'needs_review') then
    raise exception 'invalid task status' using errcode = '22023';
  end if;
  if jsonb_typeof(p_annotation) <> 'object'
     or p_annotation ->> 'schema_version' <> 'dcal.annotation.v2'
     or jsonb_typeof(p_annotation -> 'regions') <> 'array'
     or jsonb_typeof(p_annotation -> 'image_quality') <> 'array' then
    raise exception 'invalid annotation shape' using errcode = '22023';
  end if;
  if p_status = 'completed' then
    if nullif(p_annotation ->> 'document_type', '') is null
       or nullif(p_annotation ->> 'content_profile', '') is null then
      raise exception 'document type and content profile are required' using errcode = '22023';
    end if;
    if jsonb_array_length(p_annotation -> 'regions') = 0
       and (p_annotation ->> 'document_type') not in (
         'blank_or_noninformative_page',
         'duplicate_or_rephotographed_source',
         'non_clinical_cover',
         'unknown_document'
       ) then
      raise exception 'clinical pages require an annotated region' using errcode = '22023';
    end if;
  end if;

  select version, status
  into v_current_version, v_current_status
  from public.tasks
  where id = p_task_id
  for update;
  if not found then
    raise exception 'task not found' using errcode = 'P0002';
  end if;
  if v_current_version <> p_expected_version then
    raise exception 'this page was changed elsewhere; reload before saving'
      using errcode = '40001';
  end if;

  v_next_status := coalesce(
    p_status,
    case
      when v_current_status in ('unassigned', 'completed') then 'in_progress'
      else v_current_status
    end
  );
  v_completed_at := case when v_next_status = 'completed' then now() else null end;

  update public.tasks
  set annotation = p_annotation,
      status = v_next_status,
      assigned_to = v_user_id,
      assigned_to_name = v_actor_name,
      version = p_expected_version + 1,
      updated_at = now(),
      completed_at = v_completed_at
  where id = p_task_id;

  insert into public.revisions(
    task_id,
    version,
    actor_user_id,
    actor_name,
    action,
    annotation
  ) values (
    p_task_id,
    p_expected_version + 1,
    v_user_id,
    v_actor_name,
    case when p_status = 'completed' then 'complete' else 'save' end,
    p_annotation
  );

  return p_task_id;
end;
$$;

revoke all on function public.dcal_save_task(uuid, bigint, integer, jsonb, text)
  from public, anon, authenticated;
grant execute on function public.dcal_save_task(uuid, bigint, integer, jsonb, text)
  to service_role;
