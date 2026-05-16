import { handleSpeechKey } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function POST(request: Request) {
  return handleSpeechKey(request, "stt");
}
