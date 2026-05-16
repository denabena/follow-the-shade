import { auth } from "@clerk/nextjs/server";

export async function getClerkBearerToken(): Promise<string | null> {
  const session = await auth();
  if (!session.userId) {
    return null;
  }
  return session.getToken();
}
