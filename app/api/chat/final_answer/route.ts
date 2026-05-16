import { getClerkBearerToken } from "@/lib/follow-the-shade/auth";
import { handleFinalAnswer } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const token = await getClerkBearerToken();
  return handleFinalAnswer(request, token);
}
