import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "졸업축하 - 이준석",
  description: "대한민국 각지에 전하는 졸업 축하 메시지",
  openGraph: {
    title: "졸업축하 - 이준석",
    description: "대한민국 각지에 전하는 졸업 축하 메시지",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "졸업축하 코리요",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "졸업축하 - 이준석",
    description: "대한민국 각지에 전하는 졸업 축하 메시지",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
