import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";


const inter = Inter({
  variable: "--font-inter",
  display: "swap",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ChatDKU",
  description: "The chatbot assistant for DKU.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
