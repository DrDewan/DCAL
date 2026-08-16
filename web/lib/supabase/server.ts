import { createServerClient } from "@supabase/ssr";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

import { publicEnv, secretEnv } from "@/lib/env";

export async function createSessionClient() {
  const cookieStore = await cookies();
  const { supabaseUrl, supabasePublishableKey } = publicEnv();
  return createServerClient(supabaseUrl, supabasePublishableKey, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (cookiesToSet) => {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        } catch {
          // A Server Component cannot always write refreshed cookies. Mutating
          // routes and login actions can, and every API route revalidates user.
        }
      },
    },
  });
}

export function createAdminClient() {
  const { supabaseUrl, supabaseSecretKey } = secretEnv();
  return createClient(supabaseUrl, supabaseSecretKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}
