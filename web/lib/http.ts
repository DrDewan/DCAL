import { NextRequest, NextResponse } from "next/server";

export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export function jsonError(error: unknown) {
  if (error instanceof HttpError) {
    return NextResponse.json(
      { error: { code: error.code, message: error.message } },
      { status: error.status },
    );
  }
  const safeCode =
    error && typeof error === "object" && "code" in error &&
    typeof (error as { code?: unknown }).code === "string" &&
    /^[A-Za-z0-9_]{1,32}$/.test((error as { code: string }).code)
      ? (error as { code: string }).code
      : "unclassified";
  console.error("DCAL request failed", {
    error_type: error instanceof Error ? error.constructor.name : typeof error,
    error_code: safeCode,
  });
  return NextResponse.json(
    { error: { code: "internal_error", message: "The request could not be completed." } },
    { status: 500 },
  );
}

export function assertSameOrigin(request: NextRequest) {
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin") {
    throw new HttpError(403, "invalid_origin", "Cross-origin request rejected.");
  }
  const origin = request.headers.get("origin");
  if (!origin) throw new HttpError(403, "origin_required", "Request origin is required.");
  const expected = new URL(request.url);
  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedProto = request.headers.get("x-forwarded-proto");
  if (forwardedHost) expected.host = forwardedHost;
  if (forwardedProto) expected.protocol = `${forwardedProto}:`;
  let supplied: URL;
  try {
    supplied = new URL(origin);
  } catch {
    throw new HttpError(403, "invalid_origin", "Request origin is invalid.");
  }
  if (supplied.origin !== expected.origin) {
    throw new HttpError(403, "invalid_origin", "Cross-origin request rejected.");
  }
}

export async function readJsonObject(request: Request) {
  let value: unknown;
  try {
    value = await request.json();
  } catch {
    throw new HttpError(400, "invalid_json", "Request contains invalid JSON.");
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(400, "invalid_json", "JSON request must be an object.");
  }
  return value as Record<string, unknown>;
}
