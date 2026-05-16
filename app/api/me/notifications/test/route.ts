import { getClerkBearerToken } from "@/lib/follow-the-shade/auth";
import { proxyMeNotifications } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function POST() {
  const token = await getClerkBearerToken();
  if (!token) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  return proxyMeNotifications(
    new Request("http://local/me/notifications/test", { method: "POST" }),
    token,
    { bodyOverride: {}, test: true },
  );
}
