import { matchesBetaLogin } from "@/lib/beta-access";

export async function POST(request: Request) {
  const token = process.env.BETA_API_TOKEN;
  const base = process.env.API_URL;
  if (process.env.BETA_ACCESS_ENABLED !== "true" || process.env.BETA_METRICS_ENABLED !== "true" || !token || !base) {
    return new Response(null, { status: 404 });
  }
  if (!await matchesBetaLogin(request.headers.get("authorization"), process.env.BETA_ACCESS_PASSWORD ?? "")) {
    return new Response(null, { status: 401 });
  }
  if (request.headers.get("sec-fetch-site") !== "same-origin") return new Response(null, { status: 403 });
  try {
    const reader = request.body?.getReader();
    if (!reader) return new Response(null, { status: 400 });
    let body = "";
    const decoder = new TextDecoder();
    let size = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 512) {
        await reader.cancel();
        return new Response(null, { status: 413 });
      }
      body += decoder.decode(value, { stream: true });
    }
    body += decoder.decode();
    const response = await fetch(`${base.replace(/\/$/, "")}/api/v2/beta/visits`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-Beta-Api-Token": token },
      body, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(3000),
    });
    return new Response(null, { status: response.ok ? 204 : 400 });
  } catch {
    return new Response(null, { status: 503 });
  }
}
