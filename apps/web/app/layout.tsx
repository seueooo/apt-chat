import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

const geistSans = Geist({
	subsets: ["latin"],
	variable: "--font-geist-sans",
});

const geistMono = Geist_Mono({
	subsets: ["latin"],
	variable: "--font-geist-mono",
});

export const metadata: Metadata = {
	title: "AptChat — 연봉 기반 아파트 시뮬레이터",
	description: "연봉 기반 아파트 매매 시뮬레이터와 AI 챗봇으로 내 집 마련 가능성을 탐색하세요.",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="ko" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
			<body className="min-h-full font-sans">
				<Providers>{children}</Providers>
			</body>
		</html>
	);
}
