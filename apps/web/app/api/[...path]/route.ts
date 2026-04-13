import { type NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL || "http://localhost:8000";

async function proxyRequest(request: NextRequest) {
	const { pathname, search } = request.nextUrl;
	const targetUrl = `${API_BASE}${pathname}${search}`;

	const forwardHeaders: Record<string, string> = {
		"Content-Type": "application/json",
	};
	const sessionId = request.headers.get("x-session-id");
	if (sessionId) {
		forwardHeaders["X-Session-Id"] = sessionId;
	}

	try {
		const response = await fetch(targetUrl, {
			method: request.method,
			headers: forwardHeaders,
			body:
				request.method !== "GET" && request.method !== "HEAD" ? await request.text() : undefined,
		});

		const data = await response.text();

		return new NextResponse(data, {
			status: response.status,
			headers: {
				"Content-Type": response.headers.get("Content-Type") || "application/json",
			},
		});
	} catch {
		return NextResponse.json({ error: "Backend unavailable" }, { status: 502 });
	}
}

export async function GET(request: NextRequest) {
	return proxyRequest(request);
}

export async function POST(request: NextRequest) {
	return proxyRequest(request);
}
