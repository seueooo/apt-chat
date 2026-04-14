"use client";

/**
 * useChat — 챗봇 메시지 상태 + 세션당 3회 제한 + 서버 카운터 동기화.
 *
 * 핵심 규칙 (Task 12):
 *
 * 1. 초기 `remainingQuestions = getMaxQuestions()` (= 3).
 * 2. `send(content)` 는 낙관적으로 카운터를 감소시키고 유저 메시지를 즉시 추가한다.
 * 3. 성공 시 서버 응답의 `remaining_questions` 로 **반드시** 재동기화 (서버가 진실 소스).
 * 4. 429 에러 시 카운터를 0 으로 강제 동기화 — 클라이언트가 앞서가더라도 서버가 거절한 즉시 lock.
 * 5. `remainingQuestions === 0` 이거나 mutation 진행 중이면 `send` 는 no-op (연타 방지).
 * 6. 카운터는 음수를 허용하지 않는다 (`Math.max(0, ...)`).
 *
 * SSR 가드:
 * - `sessionId` 는 빈 문자열로 초기화 후 `useEffect` 에서 `getOrCreateSessionId()` 를 호출.
 *   이 방식은 서버 렌더 결과와 클라이언트 첫 렌더 결과가 동일해 hydration mismatch 를 피한다.
 */

import { useMutation } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { getMaxQuestions, getOrCreateSessionId } from "@/lib/session";
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
	send: (content: string) => void;
	remainingQuestions: number;
	isExhausted: boolean;
	error: ApiError | null;
};

function clampRemaining(value: number): number {
	return Math.max(0, Math.min(getMaxQuestions(), Math.trunc(value)));
}

export function useChat(context?: ChatContext): UseChatResult {
	const [sessionId, setSessionId] = useState<string>("");
	const [messages, setMessages] = useState<Message[]>([]);
	const [remainingQuestions, setRemainingQuestions] = useState<number>(getMaxQuestions());
	const [error, setError] = useState<ApiError | null>(null);

	// Hydration 직후 세션 ID 로드 (SSR 가드)
	useEffect(() => {
		setSessionId(getOrCreateSessionId());
	}, []);

	const mutation = useMutation<ChatResponse, Error, string>({
		mutationFn: (content: string) => {
			// 다음 turn 의 히스토리 = 기존 messages + 새 user 메시지
			const history: ChatMessage[] = [
				...messages.map((m) => ({ role: m.role, content: m.content })),
				{ role: "user" as const, content },
			];
			return api.chat({
				sessionId,
				messages: history,
				context: context ?? null,
			});
		},
		onMutate: (content: string) => {
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
		(content: string) => {
			const trimmed = content.trim();
			if (!trimmed) return;
			if (remainingQuestions === 0) return;
			if (mutation.isPending) return;

			// 낙관적 감소: UI 즉시 반영. 성공/실패 시 서버 값으로 재동기화됨.
			setRemainingQuestions((prev) => Math.max(0, prev - 1));
			mutation.mutate(trimmed);
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
