import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
 title: "AI Resume Optimizer",
 description: "Optimize your resume with AI — ATS-friendly, tailored to any job",
};

export default function RootLayout({
 children,
}: {
 children: React.ReactNode;
}) {
 return (
 <html lang="en">
 <body className={inter.className}>
 <Providers>{children}</Providers>
 </body>
 </html>
 );
}
