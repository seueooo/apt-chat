/**
 * apt-chat 프론트엔드 API 클라이언트.
 *
 * - 모든 호출은 Next.js 프록시 (`web/app/api/[...path]/route.ts`) 를 경유한다.
 *   → 상대 경로 `/api/...` 만 사용. 절대 URL/환경변수 금지.
 * - 에러는 `ApiError` 로 throw 되며, 호출자는 `error instanceof ApiError` 로
 *   narrow 해서 `status`/`detail` 을 사용할 수 있다.
 * - 세션 ID (`X-Session-Id`) 는 chat 호출에만 필요하며 Task 12의 `useChat` 훅이
 *   관리한다. 여기서는 파라미터로만 받는다.
 */

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

// --- 에러 --------------------------------------------------------------------

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

// --- 내부 헬퍼 ---------------------------------------------------------------

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * FastAPI/Next.js 프록시 에러 응답에서 사람이 읽을 수 있는 메시지를 추출한다.
 *
 * - FastAPI HTTPException → `{ detail: string }`
 * - Pydantic 422         → `{ detail: [{ loc, msg, type }, ...] }`
 * - Next.js 프록시 502    → `{ error: string }`
 */
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

	// 성공 응답 — 프록시가 Content-Type을 보존하므로 JSON 파싱 가능.
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

// --- public API -------------------------------------------------------------

export const api = {
	simulate(req: SimulateRequest): Promise<SimulateResponse> {
		return post<SimulateResponse>("/api/simulate", req);
	},

	/**
	 * 챗봇 호출. 세션 ID 는 `X-Session-Id` 헤더로 프록시를 통해 백엔드까지 전달된다.
	 *
	 * @param params.sessionId  `getOrCreateSessionId()` 결과. 빈 문자열이면 헤더 생략.
	 * @param params.messages   대화 히스토리 (역할별 turn 전체).
	 * @param params.context    선택적 컨텍스트 (시뮬레이터 상태 등). 기본 null.
	 * @param params.summarize  컨텍스트 요약 모드. 기본 false.
	 */
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
