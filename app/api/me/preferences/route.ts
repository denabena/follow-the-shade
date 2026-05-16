import { getClerkBearerToken } from "@/lib/follow-the-shade/auth";
import { proxyMePreferences } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function GET() {
  const token = await getClerkBearerToken();
  if (!token) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  return proxyMePreferences(new Request("http://local/me/preferences"), token);
}

export async function PATCH(request: Request) {
  const token = await getClerkBearerToken();
  if (!token) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  return proxyMePreferences(request, token);
}
