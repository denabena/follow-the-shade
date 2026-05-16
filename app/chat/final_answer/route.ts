import { handleFinalAnswer } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function POST(request: Request) {
  return handleFinalAnswer(request);
}
