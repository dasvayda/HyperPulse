import { NextResponse } from "next/server";
import { getPipelineStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(await getPipelineStatus(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ error: "Pipeline status unavailable" }, { status: 503 });
  }
}
