import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Aarogya Bindu — AI-Assisted Preliminary Screening",
  description:
    "Aarogya Bindu demonstrates how smartphone-based colorimetric test-strip " +
    "analysis could support accessible preliminary health screening. " +
    "SIMULATED — NOT FOR MEDICAL USE.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans`}>{children}</body>
    </html>
  );
}
