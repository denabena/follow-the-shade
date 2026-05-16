import { getClerkBearerToken } from "@/lib/follow-the-shade/auth";
import { handleSpeechKey } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const token = await getClerkBearerToken();
  return handleSpeechKey(request, "stt", token);
}
