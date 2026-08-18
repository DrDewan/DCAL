import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { workbenchMarkup } from "@/lib/workbench-markup";

// app.js binds these by id without a null check, matching the existing client
// style. If the markup and the client disagree, bindFields throws during init
// and the whole workbench fails to start, not just the affected field.
test("every element the client binds by id exists in the markup", () => {
  const markup = workbenchMarkup(true);
  const client = readFileSync(new URL("../public/app.js", import.meta.url), "utf8");
  const bound = new Set<string>();
  for (const match of client.matchAll(/\$\("#([a-z0-9-]+)"\)\s*\.addEventListener/gi)) {
    bound.add(match[1]);
  }
  assert.ok(bound.size > 5, "expected to discover several bound element ids");
  const missing = [...bound].filter((id) => !markup.includes(`id="${id}"`));
  assert.deepEqual(missing, [], `markup is missing bound ids: ${missing.join(", ")}`);
});

test("the writer section is present and export stays role gated", () => {
  const markup = workbenchMarkup(true);
  for (const id of ["writer-chips", "writer-input", "writer-add", "writer-options"]) {
    assert.ok(markup.includes(`id="${id}"`), `missing #${id}`);
  }
  assert.ok(markup.includes("/api/export/gold.jsonl"));
  assert.ok(!workbenchMarkup(false).includes("/api/export/gold.jsonl"));
});
