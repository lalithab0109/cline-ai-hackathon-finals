/**
 * SERVER-ONLY in-memory fixed-window rate limiter (per client IP + global cap).
 *
 * Limitation: state lives in this Node process only — it resets on restart
 * and is not shared across instances. Adequate for a single-instance demo;
 * a deployment would need a shared store (e.g. Redis) or an edge limiter.
 */

import "server-only";

const WINDOW_MS = 60_000;
const PER_CLIENT_LIMIT = 8; // requests per client per minute
const GLOBAL_LIMIT = 60; // requests per minute across all clients (caps spend)
const MAX_TRACKED = 5_000;

const buckets = new Map<string, { start: number; count: number }>();
let global = { start: 0, count: 0 };

export type RateLimitResult = { ok: true } | { ok: false; retryAfterSec: number };

export function checkRateLimit(clientKey: string, now = Date.now()): RateLimitResult {
  if (now - global.start >= WINDOW_MS) global = { start: now, count: 0 };
  if (global.count >= GLOBAL_LIMIT) {
    return { ok: false, retryAfterSec: Math.ceil((global.start + WINDOW_MS - now) / 1000) };
  }

  if (buckets.size > MAX_TRACKED) {
    for (const [key, b] of buckets) if (now - b.start >= WINDOW_MS) buckets.delete(key);
    if (buckets.size > MAX_TRACKED) buckets.clear();
  }
  let bucket = buckets.get(clientKey);
  if (!bucket || now - bucket.start >= WINDOW_MS) {
    bucket = { start: now, count: 0 };
    buckets.set(clientKey, bucket);
  }
  if (bucket.count >= PER_CLIENT_LIMIT) {
    return { ok: false, retryAfterSec: Math.ceil((bucket.start + WINDOW_MS - now) / 1000) };
  }
  bucket.count += 1;
  global.count += 1;
  return { ok: true };
}

/** Best-effort client key. Proxy headers are spoofable; acceptable for a demo limiter. */
export function clientKeyFrom(headers: Headers): string {
  const forwarded = headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const real = headers.get("x-real-ip")?.trim();
  return (forwarded || real || "local").slice(0, 64);
}
