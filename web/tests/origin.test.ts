import assert from "node:assert/strict";
import test from "node:test";

import { NextRequest } from "next/server";

import { assertSameOrigin, HttpError } from "@/lib/http";

const APP = "https://dcal.example.org";

function request(url: string, headers: Record<string, string>) {
  return new NextRequest(new Request(url, { method: "POST", headers }));
}

function withConfiguredOrigin<T>(value: string | undefined, run: () => T): T {
  const previous = process.env.DCAL_APP_ORIGIN;
  if (value === undefined) delete process.env.DCAL_APP_ORIGIN;
  else process.env.DCAL_APP_ORIGIN = value;
  try {
    return run();
  } finally {
    if (previous === undefined) delete process.env.DCAL_APP_ORIGIN;
    else process.env.DCAL_APP_ORIGIN = previous;
  }
}

test("a configured origin accepts its own origin", () => {
  withConfiguredOrigin(APP, () => {
    assertSameOrigin(request(`${APP}/api/tasks`, { origin: APP }));
  });
});

test("a configured origin ignores a spoofed forwarded host", () => {
  withConfiguredOrigin(APP, () => {
    assert.throws(
      () => assertSameOrigin(request(`${APP}/api/tasks`, {
        origin: "https://attacker.example",
        "x-forwarded-host": "attacker.example",
        "x-forwarded-proto": "https",
      })),
      (error) => error instanceof HttpError && error.status === 403,
    );
  });
});

test("a configured allowlist may hold more than one origin", () => {
  withConfiguredOrigin(`${APP},https://staging.example.org`, () => {
    assertSameOrigin(request(`${APP}/api/tasks`, { origin: "https://staging.example.org" }));
  });
});

test("without configuration the proxy-reported host is still honoured", () => {
  withConfiguredOrigin(undefined, () => {
    assertSameOrigin(request("http://internal.local/api/tasks", {
      origin: "https://preview.vercel.app",
      "x-forwarded-host": "preview.vercel.app",
      "x-forwarded-proto": "https",
    }));
  });
});

test("a cross-site fetch metadata header is rejected outright", () => {
  withConfiguredOrigin(APP, () => {
    assert.throws(
      () => assertSameOrigin(request(`${APP}/api/tasks`, {
        origin: APP,
        "sec-fetch-site": "cross-site",
      })),
      (error) => error instanceof HttpError && error.status === 403,
    );
  });
});

test("a missing origin header is rejected", () => {
  withConfiguredOrigin(APP, () => {
    assert.throws(
      () => assertSameOrigin(request(`${APP}/api/tasks`, {})),
      (error) => error instanceof HttpError && error.code === "origin_required",
    );
  });
});
