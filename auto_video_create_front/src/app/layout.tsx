// 'use client';

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import ClientLayout from "./ClientLayout";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "블로그 글로 숏폼 만들기",
  description: "블로그 글 주소만 넣으면 숏폼이 만들어집니다.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // lang 은 "ko" 여야 한다. 콘텐츠가 전부 한국어인데 "en" 으로 선언돼 있으면
  // 크롬이 "영어 페이지에 한국어가 있다" 고 보고 자동 번역을 건다. 구글 번역은
  // 텍스트 노드를 통째로 갈아치우므로, React 가 나중에 그 노드를 지우려 할 때
  // removeChild NotFoundError 로 터진다 (2026-08-20 Sentry JAVASCRIPT-NEXTJS-3).
  return (
    <html lang="ko">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
