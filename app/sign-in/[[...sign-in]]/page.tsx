import { SignIn } from "@clerk/nextjs";
import Image from "next/image";
import backgroundImage from "@/assets/background.png";

export default function SignInPage() {
  return (
    <main className="relative min-h-screen w-full overflow-x-hidden bg-bone">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-[1] opacity-[0.06]"
      >
        <Image
          src={backgroundImage}
          alt=""
          fill
          priority
          sizes="100vw"
          className="h-full w-full object-cover object-center"
        />
      </div>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -left-20 top-0 h-[45vmin] w-[45vmin] rounded-full bg-ink/10 blur-3xl" />
      </div>

      <div className="relative z-[2] flex min-h-screen items-center justify-center px-4 py-12">
        <div className="w-full max-w-[420px]">
          <SignIn routing="path" path="/sign-in" signUpUrl="/sign-in" />
        </div>
      </div>
    </main>
  );
}
