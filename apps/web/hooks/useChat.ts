"use client";

/**
 * useChat — 챗봇 메시지 상태 + 세션당 3회 제한 + 서버 카운터 동기화.
 *
 * 핵심 규칙 (Task 12):
 *
 * 1. 초기 `remainingQuestions = MAX_QUESTIONS_PER_SESSION` (= 3).
 * 2. `send(content, context)` 는 낙관적으로 카운터를 감소시키고 유저 메시지를 즉시 추가한다.
 * 3. 성공 시 서버 응답의 `remaining_questions` 로 **반드시** 재동기화 (서버가 진실 소스).
 * 4. 429 에러 시 카운터를 0 으로 강제 동기화 — 클라이언트가 앞서가더라도 서버가 거절한 즉시 lock.
 * 5. `remainingQuestions === 0` 이거나 mutation 진행 중이면 `send` 는 no-op (연타 방지).
 * 6. 카운터는 음수를 허용하지 않는다 (`Math.max(0, ...)`).
 *
 * Context 전달 방식:
 * - 과거에는 `useChat(context)` 로 hook 파라미터로 받아 매 렌더마다 context 를 재구독했다.
 *   이 방식은 ChatWindow 가 시뮬레이터 store 를 selector 로 구독해야 하므로, 결과가
 *   업데이트될 때마다 ChatWindow 본체가 리렌더되는 부작용이 있었다.
 * - 현재 방식: `send(content, context)` 시점에만 context 를 전달. ChatWindow 는 store 에서
 *   render-time 구독 없이 `store.getSnapshot()` 으로 snapshot 만 읽어 context 를 조립.
 *
 * SSR 가드:
 * - `getOrCreateSessionId()` 는 `mutationFn` 내부에서 lazy 하게 호출된다. mutation 은
 *   사용자 action(클릭/전송) 이후에만 실행되므로 이미 hydration 이 끝난 시점이며,
 *   `useEffect` 를 통한 상태 동기화 없이도 항상 유효한 session id 를 얻는다.
 */

import { useMutation } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { getOrCreateSessionId, MAX_QUESTIONS_PER_SESSION } from "@/lib/session";
import type { ChatContext, ChatMessage, ChatResponse } from "@/lib/types";

export type UserMessage = {
	role: "user";
	content: string;
};

export type AssistantMessage = {
	role: "assistant";
	content: string;
	data?: ChatResponse;
};

export type Message = UserMessage | AssistantMessage;

export type UseChatResult = {
	messages: Message[];
	loading: boolean;
	send: (content: string, context: ChatContext | null) => void;
	remainingQuestions: number;
	isExhausted: boolean;
	error: ApiError | null;
};

type SendVariables = {
	content: string;
	context: ChatContext | null;
};

function clampRemaining(value: number): number {
	return Math.max(0, Math.min(MAX_QUESTIONS_PER_SESSION, Math.trunc(value)));
}

export function useChat(): UseChatResult {
	const [messages, setMessages] = useState<Message[]>([]);
	const [remainingQuestions, setRemainingQuestions] = useState<number>(MAX_QUESTIONS_PER_SESSION);
	const [error, setError] = useState<ApiError | null>(null);

	const mutation = useMutation<ChatResponse, Error, SendVariables>({
		mutationFn: ({ content, context }: SendVariables) => {
			// 다음 turn 의 히스토리 = 기존 messages + 새 user 메시지
			const history: ChatMessage[] = [
				...messages.map((m) => ({ role: m.role, content: m.content })),
				{ role: "user" as const, content },
			];
			// mutationFn 은 사용자 action 이후에만 실행되므로 브라우저 컨텍스트가 보장됨.
			return api.chat({
				sessionId: getOrCreateSessionId(),
				messages: history,
				context,
			});
		},
		onMutate: ({ content }: SendVariables) => {
			setError(null);
			setMessages((prev) => [...prev, { role: "user", content }]);
		},
		onSuccess: (response) => {
			setMessages((prev) => [
				...prev,
				{ role: "assistant", content: response.answer, data: response },
			]);
			// 서버 카운터로 재동기화 — 이것이 진실 소스.
			setRemainingQuestions(clampRemaining(response.remaining_questions));
		},
		onError: (err) => {
			if (err instanceof ApiError) {
				setError(err);
				if (err.status === 429) {
					setRemainingQuestions(0);
				}
			} else {
				setError(new ApiError(0, null, err.message || "알 수 없는 오류"));
			}
		},
	});

	const send = useCallback(
		(content: string, context: ChatContext | null) => {
			const trimmed = content.trim();
			if (!trimmed) return;
			if (remainingQuestions === 0) return;
			if (mutation.isPending) return;

			// 낙관적 감소: UI 즉시 반영. 성공/실패 시 서버 값으로 재동기화됨.
			setRemainingQuestions((prev) => Math.max(0, prev - 1));
			mutation.mutate({ content, context });
		},
		[remainingQuestions, mutation],
	);

	return {
		messages,
		loading: mutation.isPending,
		send,
		remainingQuestions,
		isExhausted: remainingQuestions === 0,
		error,
	};
}
