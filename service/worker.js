const PLAN_IDS = new Set(["short-term", "long-term", "perfect"]);
const PLAN_LIMITS = {
  "short-term": { score: 75, blocked: ["HIGH"] },
  "long-term": { score: 80, blocked: ["HIGH"] },
  perfect: { score: 90, blocked: ["HIGH", "MED"] },
};
const now = () => Math.floor(Date.now() / 1000);
const id = () => crypto.randomUUID();
const json = (value, status = 200, headers = {}) => new Response(JSON.stringify(value), {
  status, headers: { "content-type": "application/json; charset=utf-8", ...headers },
});
function cors(request, env) {
  const origin = request.headers.get("origin") || "*";
  const allowed = String(env.ALLOWED_ORIGINS || "*").split(",").map(x => x.trim());
  return allowed.includes("*") || allowed.includes(origin) ? {
    "access-control-allow-origin": allowed.includes("*") ? "*" : origin,
    "access-control-allow-headers": "authorization,content-type",
    "access-control-allow-methods": "GET,POST,OPTIONS",
  } : {};
}
async function digest(value) {
  const bytes = new TextEncoder().encode(value);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2, "0")).join("");
}
function b64(value) { return btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
function unb64(value) { const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((value.length + 3) % 4); return Uint8Array.from(atob(padded), c => c.charCodeAt(0)); }
async function sign(payload, secret) {
  const body = b64(new TextEncoder().encode(JSON.stringify(payload)));
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  return `${body}.${b64(signature)}`;
}
async function verify(token, secret) {
  const [body, supplied] = String(token || "").split(".");
  if (!body || !supplied) return null;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["verify"]);
  if (!await crypto.subtle.verify("HMAC", key, unb64(supplied), new TextEncoder().encode(body))) return null;
  try { const payload = JSON.parse(new TextDecoder().decode(unb64(body))); return payload.exp > now() ? payload : null; } catch (_) { return null; }
}
async function bodyJson(request, env) {
  const limit = Number(env.MAX_SUMMARY_BYTES || 262144);
  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > limit) throw new Error("request too large");
  return JSON.parse(text);
}
async function authenticate(request, env) {
  const header = request.headers.get("authorization") || "";
  const payload = await verify(header.startsWith("Bearer ") ? header.slice(7) : "", env.TOKEN_SECRET || "development-only-secret");
  if (!payload) throw new Error("unauthorized");
  const session = await env.DB.prepare("SELECT * FROM sessions WHERE id = ? AND revoked = 0").bind(payload.sid).first();
  if (!session || session.expires_at <= now()) throw new Error("session expired");
  return payload;
}
async function adminAuthorized(request, env) {
  const supplied = request.headers.get("x-admin-token") || "";
  if (!supplied || !env.ADMIN_TOKEN) return false;
  return (await digest(supplied)) === (await digest(String(env.ADMIN_TOKEN)));
}
function newInviteCode() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = new Uint8Array(18);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, byte => alphabet[byte % alphabet.length]).join("").match(/.{1,6}/g).join("-");
}
function safeSummary(input) {
  if (!input || typeof input !== "object") throw new Error("summary must be an object");
  return {
    schema: "architecture-review-summary/v1",
    projectHash: String(input.projectHash || "").slice(0, 128),
    architectureScore: Number.isFinite(Number(input.architectureScore)) ? Number(input.architectureScore) : null,
    modules: Array.isArray(input.modules) ? input.modules.slice(0, 500).map(module => ({
      id: String(module.id || "").slice(0, 160),
      score: Number.isFinite(Number(module.score)) ? Number(module.score) : null,
      grade: String(module.grade || "").slice(0, 20),
      severities: Array.isArray(module.severities) ? module.severities.map(x => String(x).slice(0, 12)).slice(0, 20) : [],
      tags: Array.isArray(module.tags) ? module.tags.map(x => String(x).slice(0, 60)).slice(0, 20) : [],
      codeLines: Number.isFinite(Number(module.codeLines)) ? Number(module.codeLines) : null,
    })) : [],
  };
}
function tasksFor(summary, planId) {
  const limits = PLAN_LIMITS[planId];
  return summary.modules.filter(module => module.score == null || module.score < limits.score || module.severities.some(x => limits.blocked.includes(x)))
    .sort((a, b) => (a.score ?? -1) - (b.score ?? -1)).map((module, index) => ({ id: `task-${index + 1}`, moduleId: module.id, targetScore: limits.score, blockedSeverities: limits.blocked, status: "queued" }));
}
async function route(request, env) {
  const url = new URL(request.url); const path = url.pathname.replace(/\/+$/, "") || "/";
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(request, env) });
  if (path === "/health" && request.method === "GET") return json({ ok: true, service: "architecture-review-plus" }, 200, cors(request, env));
  if (path === "/v1/invites/redeem" && request.method === "POST") {
    const input = await bodyJson(request, env); const codeHash = await digest(String(input.code || ""));
    const invite = await env.DB.prepare("SELECT * FROM invites WHERE code_hash = ? AND revoked = 0").bind(codeHash).first();
    if (!invite || (invite.expires_at && invite.expires_at <= now()) || invite.used_count >= invite.max_uses) return json({ error: "invalid_or_expired_invite" }, 403, cors(request, env));
    const subject = `plus-${id()}`; const sessionId = id(); const expiresAt = now() + Number(env.TOKEN_TTL_SECONDS || 86400);
    await env.DB.batch([
      env.DB.prepare("UPDATE invites SET used_count = used_count + 1 WHERE code_hash = ?").bind(codeHash),
      env.DB.prepare("INSERT INTO sessions (id, subject, device_id, expires_at, created_at) VALUES (?, ?, ?, ?, ?)").bind(sessionId, subject, String(input.deviceId || "unknown").slice(0, 160), expiresAt, now()),
    ]);
    return json({ token: await sign({ sid: sessionId, sub: subject, exp: expiresAt, scope: "plus" }, env.TOKEN_SECRET || "development-only-secret"), expiresAt, scope: "plus" }, 200, cors(request, env));
  }
  if (path === "/v1/admin/invites" && request.method === "POST") {
    if (!await adminAuthorized(request, env)) return json({ error: "admin_unauthorized" }, 401, cors(request, env));
    const input = await bodyJson(request, env);
    const code = newInviteCode();
    const maxUses = Math.max(1, Math.min(1000, Number(input.maxUses || 1)));
    const expiresAt = input.expiresAt == null ? null : Number(input.expiresAt);
    await env.DB.prepare("INSERT INTO invites (code_hash, label, max_uses, expires_at, created_at) VALUES (?, ?, ?, ?, ?)")
      .bind(await digest(code), String(input.label || "").slice(0, 160), maxUses, expiresAt, now()).run();
    return json({ code, maxUses, expiresAt }, 201, cors(request, env));
  }
  let identity; try { identity = await authenticate(request, env); } catch (_) { return json({ error: "unauthorized" }, 401, cors(request, env)); }
  if (path === "/v1/audit-summaries" && request.method === "POST") {
    const summary = safeSummary(await bodyJson(request, env)); if (!summary.projectHash) return json({ error: "projectHash_required" }, 400, cors(request, env));
    const auditId = id(); await env.DB.prepare("INSERT INTO audits (id, subject, project_hash, summary_json, created_at) VALUES (?, ?, ?, ?, ?)").bind(auditId, identity.sub, summary.projectHash, JSON.stringify(summary), now()).run();
    return json({ auditId, received: { modules: summary.modules.length, sourceUploaded: false } }, 201, cors(request, env));
  }
  if (path === "/v1/repair-jobs" && request.method === "POST") {
    const input = await bodyJson(request, env); if (!PLAN_IDS.has(input.planId)) return json({ error: "invalid_plan" }, 400, cors(request, env));
    const audit = await env.DB.prepare("SELECT * FROM audits WHERE id = ? AND subject = ?").bind(String(input.auditId || ""), identity.sub).first(); if (!audit) return json({ error: "audit_not_found" }, 404, cors(request, env));
    const tasks = tasksFor(JSON.parse(audit.summary_json), input.planId); const jobId = id(); const status = tasks.length ? "queued" : "completed";
    await env.DB.prepare("INSERT INTO repair_jobs (id, subject, audit_id, plan_id, status, tasks_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)").bind(jobId, identity.sub, audit.id, input.planId, status, JSON.stringify(tasks), now(), now()).run();
    return json({ jobId, status, tasks, sourceUploaded: false }, 201, cors(request, env));
  }
  const jobMatch = path.match(/^\/v1\/repair-jobs\/([^/]+)$/);
  if (jobMatch && request.method === "GET") {
    const job = await env.DB.prepare("SELECT * FROM repair_jobs WHERE id = ? AND subject = ?").bind(jobMatch[1], identity.sub).first(); if (!job) return json({ error: "job_not_found" }, 404, cors(request, env));
    const events = await env.DB.prepare("SELECT task_id AS taskId, status, detail, created_at AS createdAt FROM repair_events WHERE job_id = ? ORDER BY id ASC").bind(job.id).all();
    return json({ jobId: job.id, planId: job.plan_id, status: job.status, tasks: JSON.parse(job.tasks_json), events: events.results, sourceUploaded: false }, 200, cors(request, env));
  }
  const eventMatch = path.match(/^\/v1\/repair-jobs\/([^/]+)\/events$/);
  if (eventMatch && request.method === "POST") {
    const job = await env.DB.prepare("SELECT * FROM repair_jobs WHERE id = ? AND subject = ?").bind(eventMatch[1], identity.sub).first(); if (!job) return json({ error: "job_not_found" }, 404, cors(request, env));
    const input = await bodyJson(request, env); const allowed = new Set(["queued", "planning", "repairing", "completed", "failed", "cancelled"]); if (!allowed.has(input.status)) return json({ error: "invalid_status" }, 400, cors(request, env));
    await env.DB.batch([
      env.DB.prepare("INSERT INTO repair_events (job_id, task_id, status, detail, created_at) VALUES (?, ?, ?, ?, ?)").bind(job.id, String(input.taskId || "").slice(0, 160), input.status, String(input.detail || "").slice(0, 1000), now()),
      env.DB.prepare("UPDATE repair_jobs SET status = ?, updated_at = ? WHERE id = ?").bind(input.status, now(), job.id),
    ]); return json({ ok: true }, 202, cors(request, env));
  }
  return json({ error: "not_found" }, 404, cors(request, env));
}
export default { async fetch(request, env) { try { return await route(request, env); } catch (error) { return json({ error: "bad_request", message: String(error.message || error) }, 400, cors(request, env)); } };
