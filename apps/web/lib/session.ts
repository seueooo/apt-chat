/**
 * 세션 ID 관리 — 탭별 sessionStorage 기반 UUID + 세션당 질문 상한.
 *
 * - `sessionStorage` 사용 → 같은 탭 유지, 새 탭/창 닫기 시 리셋 (새로고침은 유지).
 * - SSR 가드: 서버 환경(`typeof window === "undefined"`)에서는 빈 문자열을 반환하여
 *   Next.js의 server 렌더링 중 예외를 방지한다. 소비자(useChat)는 `mutationFn` 내부
 *   (= 사용자 action 이후 = 브라우저 컨텍스트 보장) 에서 lazy 하게 호출한다.
 * - `crypto.randomUUID` 가 없는 레거시/비-HTTPS 환경을 위한 fallback 포함.
 *
 * Plan Task 12: "비용 제어 + 보안 원칙 ⑤(클라이언트 제한)" — 서버 rate limit과 이중 보호.
 */

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

/**
 * 현재 탭의 세션 ID를 반환한다. 없으면 새로 생성해 `sessionStorage` 에 저장.
 *
 * SSR 환경(서버 렌더) 에서는 빈 문자열 `""` 을 반환한다. 이 함수는 사용자 action
 * 이후(mutation 실행 중 등) lazy 하게 호출하는 것이 가장 안전하다.
 */
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
