import { getClerkBearerToken } from "@/lib/follow-the-shade/auth";
import { handlePlacePhoto } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const token = await getClerkBearerToken();
  return handlePlacePhoto(request, token);
}
