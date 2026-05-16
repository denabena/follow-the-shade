import { auth, clerkClient } from "@clerk/nextjs/server";
import { proxyMeNotifications } from "@/lib/follow-the-shade/route-handlers";

export const runtime = "nodejs";

export async function GET() {
  const session = await auth();
  if (!session.userId) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  return proxyMeNotifications(
    new Request("http://local/me/notifications"),
    await session.getToken(),
  );
}

export async function PUT(request: Request) {
  const session = await auth();
  if (!session.userId) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  if (!body.email) {
    const client = await clerkClient();
    const user = await client.users.getUser(session.userId);
    body.email =
      user.primaryEmailAddress?.emailAddress ??
      user.emailAddresses[0]?.emailAddress;
  }

  return proxyMeNotifications(
    new Request("http://local/me/notifications", { method: "PUT" }),
    await session.getToken(),
    { bodyOverride: body },
  );
}
