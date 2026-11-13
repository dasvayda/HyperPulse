import { NextResponse, type NextRequest } from "next/server";
import { matchesBetaLogin } from "./lib/beta-access";

export async function middleware(request: NextRequest) {
  if (process.env.BETA_ACCESS_ENABLED !== "true") return NextResponse.next();
  const headers = { "Cache-Control": "private, no-store", Vary: "Authorization" };
  const password = process.env.BETA_ACCESS_PASSWORD;
  if (!password || !process.env.BETA_API_TOKEN) {
    return new NextResponse("Beta access is not configured", { status: 503, headers });
  }
  if (!(await matchesBetaLogin(request.headers.get("authorization"), password))) {
    return new NextResponse("Beta access required", {
      status: 401,
      headers: { ...headers, "WWW-Authenticate": 'Basic realm="HyperPulse Beta", charset="UTF-8"' },
    });
  }
  const response = NextResponse.next();
  response.headers.set("Cache-Control", headers["Cache-Control"]);
  response.headers.append("Vary", "Authorization");
  return response;
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
