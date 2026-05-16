import type { Metadata } from "next"
import { ClerkProvider } from "@clerk/nextjs"
import { Fraunces, Geist } from "next/font/google"
import "mapbox-gl/dist/mapbox-gl.css"
import "./globals.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap"
})

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
  axes: ["SOFT", "WONK", "opsz"]
})

export const metadata: Metadata = {
  title: "Follow the Shade",
  description:
    "Find a Split terrace venue in the sun, or in the shade, for the exact hour you want to sit outside. The browser simulates real shadows cast by the city around you.",
  icons: {
    icon: "/favicon.ico"
  }
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body
        className="bg-bone text-ink min-h-full"
        suppressHydrationWarning
      >
        <ClerkProvider>{children}</ClerkProvider>
      </body>
    </html>
  )
}
