import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

const inter = Inter({
	subsets: ["latin"],
	variable: "--font-inter",
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
		<html lang="ko" className={`${inter.variable} h-full`}>
			<body className="min-h-full font-sans">
				<Providers>{children}</Providers>
			</body>
		</html>
	);
}
