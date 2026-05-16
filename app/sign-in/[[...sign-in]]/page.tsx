import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-bone px-4">
      <SignIn routing="path" path="/sign-in" signUpUrl="/sign-in" />
    </main>
  );
}
