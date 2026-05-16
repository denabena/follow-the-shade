import { handleAnalysis } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ analysis_id: string }> },
) {
  const { analysis_id } = await params;
  return handleAnalysis(request, analysis_id);
}
