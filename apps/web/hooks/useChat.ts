"use client";

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
			const history: ChatMessage[] = [
				...messages.map((m) => ({ role: m.role, content: m.content })),
				{ role: "user" as const, content },
			];
			// mutationFn 은 user action 이후 실행 → 브라우저 컨텍스트 보장, session id lazy 획득.
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
			// 서버 카운터가 진실 소스 — 낙관적 감소분을 덮어쓴다.
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

			// 낙관적 감소 — onSuccess 가 서버 값으로 재동기화.
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
