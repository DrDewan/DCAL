const REQUIRED_PUBLIC = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
] as const;

export function publicEnv() {
  const values = Object.fromEntries(
    REQUIRED_PUBLIC.map((name) => [name, process.env[name]?.trim()]),
  ) as Record<(typeof REQUIRED_PUBLIC)[number], string | undefined>;
  const missing = REQUIRED_PUBLIC.filter((name) => !values[name]);
  if (missing.length) {
    throw new Error(`Missing deployment configuration: ${missing.join(", ")}`);
  }
  let url: URL;
  try {
    url = new URL(values.NEXT_PUBLIC_SUPABASE_URL!);
  } catch {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL must be a valid URL");
  }
  if (url.protocol !== "https:" && url.hostname !== "127.0.0.1" && url.hostname !== "localhost") {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL must use HTTPS outside local development");
  }
  if (!values.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!.startsWith("sb_publishable_")) {
    throw new Error("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY must use a modern publishable key");
  }
  return {
    supabaseUrl: values.NEXT_PUBLIC_SUPABASE_URL!,
    supabasePublishableKey: values.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  };
}

export function secretEnv() {
  const secretKey = process.env.SUPABASE_SECRET_KEY?.trim();
  if (!secretKey?.startsWith("sb_secret_")) {
    throw new Error("SUPABASE_SECRET_KEY must use a modern server-only secret key");
  }
  return { ...publicEnv(), supabaseSecretKey: secretKey };
}

export function ingestionToken() {
  const token = process.env.DCAL_WORKBENCH_INGEST_TOKEN?.trim();
  if (!token || token.length < 32) {
    throw new Error("DCAL_WORKBENCH_INGEST_TOKEN must contain at least 32 characters");
  }
  return token;
}
