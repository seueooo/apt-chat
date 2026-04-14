// 모든 호출은 Next.js 프록시 경유 — 상대 경로 `/api/...` 만 사용, 절대 URL 금지.

import type {
	ChatContext,
	ChatMessage,
	ChatRequest,
	ChatResponse,
	Region,
	SimulateRequest,
	SimulateResponse,
	StatsResponse,
} from "@/lib/types";

export class ApiError extends Error {
	readonly status: number;
	readonly detail: unknown;

	constructor(status: number, detail: unknown, message: string) {
		super(message);
		this.name = "ApiError";
		this.status = status;
		this.detail = detail;
	}
}

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

// Backend 에러 응답 envelope 변종 대응:
//   FastAPI HTTPException → { detail: string }
//   Pydantic 422          → { detail: [{ loc, msg, type }, ...] }
//   Next.js 프록시 502     → { error: string }
function extractErrorMessage(payload: unknown, fallback: string): string {
	if (!isRecord(payload)) {
		return fallback;
	}

	const detail = payload.detail;
	if (typeof detail === "string") {
		return detail;
	}
	if (Array.isArray(detail) && detail.length > 0) {
		const first = detail[0];
		if (isRecord(first) && typeof first.msg === "string") {
			return first.msg;
		}
		try {
			return JSON.stringify(detail);
		} catch {
			return fallback;
		}
	}

	const error = payload.error;
	if (typeof error === "string") {
		return error;
	}

	return fallback;
}

async function parseJsonSafely(response: Response): Promise<unknown> {
	try {
		return await response.json();
	} catch {
		return null;
	}
}

async function handleResponse<T>(response: Response): Promise<T> {
	if (!response.ok) {
		const payload = await parseJsonSafely(response);
		const fallback = response.statusText || `HTTP ${response.status}`;
		const message = extractErrorMessage(payload, fallback);
		throw new ApiError(response.status, payload, message);
	}

	return (await response.json()) as T;
}

async function post<T>(path: string, body: unknown, headers?: Record<string, string>): Promise<T> {
	const response = await fetch(path, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			...headers,
		},
		body: JSON.stringify(body),
	});
	return handleResponse<T>(response);
}

async function get<T>(path: string): Promise<T> {
	const response = await fetch(path, { method: "GET" });
	return handleResponse<T>(response);
}

export const api = {
	simulate(req: SimulateRequest): Promise<SimulateResponse> {
		return post<SimulateResponse>("/api/simulate", req);
	},

	// sessionId 가 빈 문자열이면 `X-Session-Id` 헤더 생략 (SSR fallback 경로).
	chat(params: {
		sessionId: string;
		messages: ChatMessage[];
		context?: ChatContext | null;
		summarize?: boolean;
	}): Promise<ChatResponse> {
		const body: ChatRequest = {
			messages: params.messages,
			context: params.context ?? null,
			summarize: params.summarize ?? false,
		};
		const headers: Record<string, string> = {};
		if (params.sessionId) {
			headers["X-Session-Id"] = params.sessionId;
		}
		return post<ChatResponse>("/api/chat", body, headers);
	},

	async regions(): Promise<Region[]> {
		const data = await get<{ regions: Region[] }>("/api/regions");
		return data.regions;
	},

	stats(): Promise<StatsResponse> {
		return get<StatsResponse>("/api/stats");
	},
};
