// sessionStorage 기반 — 같은 탭 유지, 탭 닫기 시 리셋 (새로고침은 유지).
// 서버 rate limit 과 이중 보호하는 클라이언트 한도.

export const SESSION_KEY = "apt-chat-session-id";
export const MAX_QUESTIONS_PER_SESSION = 3;

function generateSessionId(): string {
	if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
		return crypto.randomUUID();
	}
	// fallback: RFC4122 v4-ish — localhost/HTTP 등 crypto.randomUUID 미지원 환경용
	return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
		const r = (Math.random() * 16) | 0;
		const v = c === "x" ? r : (r & 0x3) | 0x8;
		return v.toString(16);
	});
}

// SSR 에서는 `""` 반환 — 소비자는 user action 이후 (mutationFn 내부) 에서 lazy 호출.
export function getOrCreateSessionId(): string {
	if (typeof window === "undefined") {
		return "";
	}
	try {
		let id = window.sessionStorage.getItem(SESSION_KEY);
		if (!id) {
			id = generateSessionId();
			window.sessionStorage.setItem(SESSION_KEY, id);
		}
		return id;
	} catch {
		// private 모드 등 sessionStorage 접근 불가 예외
		return "";
	}
}
