"use client";

/**
 * ChatWindow — 챗봇 메인 컨테이너.
 *
 * - `useChat(context)` 훅을 통해 메시지 상태 / 낙관적 카운터 / mutation 상태를 가져온다.
 * - 메시지가 없으면 hero + SampleQuestions + ContextBadge 노출.
 * - 있으면 메시지 목록 + 입력창.
 * - 한글 IME: `e.nativeEvent.isComposing` 체크 필수.
 * - 소진(`isExhausted`) 시 입력창/샘플 버튼 모두 disabled + 경고 배너.
 */

import { useRef, useState } from "react";
import { ContextBadge } from "@/components/Chat/ContextBadge";
import { MessageBubble } from "@/components/Chat/MessageBubble";
import { SampleQuestions } from "@/components/Chat/SampleQuestions";
import { type Message, useChat } from "@/hooks/useChat";
import { getMaxQuestions } from "@/lib/session";
import type { ChatContext } from "@/lib/types";

type ChatWindowProps = {
	context?: ChatContext;
	contextRegion?: string;
	contextBudget?: number;
};

const MAX_QUESTIONS = getMaxQuestions();

export function ChatWindow({ context, contextRegion, contextBudget }: ChatWindowProps) {
	const { messages, loading, send, remainingQuestions, isExhausted, error } = useChat(context);
	const [input, setInput] = useState<string>("");
	const textareaRef = useRef<HTMLTextAreaElement | null>(null);

	const canSend = !isExhausted && !loading && input.trim().length > 0;

	const handleSend = (): void => {
		if (!canSend) return;
		const value = input;
		setInput("");
		send(value);
	};

	const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
		// 한글 IME 조합 중 Enter 는 무시 (조합 확정용 Enter 이므로 전송 X)
		if (event.nativeEvent.isComposing) return;
		if (event.key === "Enter" && !event.shiftKey) {
			event.preventDefault();
			handleSend();
		}
	};

	const handleSampleSelect = (question: string): void => {
		if (isExhausted || loading) return;
		setInput("");
		send(question);
		textareaRef.current?.focus();
	};

	return (
		<div className="flex h-full min-h-0 flex-col gap-4">
			<Header
				remainingQuestions={remainingQuestions}
				contextRegion={contextRegion}
				contextBudget={contextBudget}
			/>

			<div className="flex min-h-0 flex-1 flex-col gap-4">
				<MessageList
					messages={messages}
					loading={loading}
					isEmpty={messages.length === 0}
					isExhausted={isExhausted}
					onSampleSelect={handleSampleSelect}
				/>

				{error ? <ErrorBanner message={error.message} /> : null}
				{isExhausted ? <ExhaustedBanner /> : null}

				<Composer
					inputRef={textareaRef}
					value={input}
					onChange={setInput}
					onSubmit={handleSend}
					onKeyDown={handleKeyDown}
					disabled={isExhausted}
					loading={loading}
					canSend={canSend}
				/>
			</div>
		</div>
	);
}

// ---- 내부 서브 컴포넌트 ----------------------------------------------------

function Header({
	remainingQuestions,
	contextRegion,
	contextBudget,
}: {
	remainingQuestions: number;
	contextRegion?: string;
	contextBudget?: number;
}) {
	const warningThreshold = remainingQuestions <= 1;
	const badgeToneClass = warningThreshold ? "text-warning" : "text-tertiary";

	return (
		<div className="flex flex-wrap items-center justify-between gap-3">
			<div className="flex flex-wrap items-center gap-2">
				<ContextBadge region={contextRegion} budget={contextBudget} />
			</div>
			<div
				className={`inline-flex items-center gap-1.5 rounded-pill bg-control-active px-3 py-1 text-[11px] font-medium tabular-nums ${badgeToneClass}`}
				aria-live="polite"
			>
				<span className="uppercase tracking-[0.08em]">남은 질문</span>
				<span>
					{remainingQuestions}/{MAX_QUESTIONS}
				</span>
			</div>
		</div>
	);
}

function MessageList({
	messages,
	loading,
	isEmpty,
	isExhausted,
	onSampleSelect,
}: {
	messages: Message[];
	loading: boolean;
	isEmpty: boolean;
	isExhausted: boolean;
	onSampleSelect: (question: string) => void;
}) {
	if (isEmpty) {
		return (
			<div className="flex min-h-0 flex-1 flex-col justify-between gap-6 rounded-lg border border-border-subtle bg-control p-6">
				<div className="flex flex-col gap-2">
					<h3 className="text-lg font-medium tracking-[-0.24px] text-primary">
						무엇이 궁금하세요?
					</h3>
					<p className="text-sm leading-relaxed text-tertiary">
						자연어로 질문하면 실거래가 데이터에서 바로 답을 찾아 드립니다. 차트와 표가 필요한 질문은
						자동으로 시각화됩니다.
					</p>
				</div>
				<SampleQuestions onSelect={onSampleSelect} disabled={isExhausted} />
			</div>
		);
	}

	return (
		<div
			className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto rounded-lg border border-border-subtle bg-control p-4"
			aria-busy={loading}
			aria-live="polite"
		>
			{messages.map((msg, idx) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: messages append-only, index stable per session
				<MessageBubble key={`msg-${idx}`} message={msg} />
			))}
			{loading ? <TypingIndicator /> : null}
		</div>
	);
}

function TypingIndicator() {
	return (
		<div className="flex justify-start">
			<div className="inline-flex items-center gap-2 rounded-lg border border-border-subtle bg-panel px-4 py-3">
				<span className="inline-flex gap-1">
					<span className="inline-block h-1.5 w-1.5 animate-pulse rounded-pill bg-tertiary" />
					<span
						className="inline-block h-1.5 w-1.5 animate-pulse rounded-pill bg-tertiary"
						style={{ animationDelay: "150ms" }}
					/>
					<span
						className="inline-block h-1.5 w-1.5 animate-pulse rounded-pill bg-tertiary"
						style={{ animationDelay: "300ms" }}
					/>
				</span>
				<span className="text-xs text-tertiary">분석 중...</span>
			</div>
		</div>
	);
}

function ErrorBanner({ message }: { message: string }) {
	return (
		<div
			role="alert"
			className="rounded-md border border-border-default bg-control px-4 py-3 text-xs text-warning"
		>
			{message}
		</div>
	);
}

function ExhaustedBanner() {
	return (
		<div
			role="status"
			className="rounded-md border border-border-default bg-control px-4 py-3 text-[11px] leading-relaxed text-tertiary"
		>
			비용 제어를 위해 세션당 질문 수를 {MAX_QUESTIONS}회로 제한합니다. 새 탭을 열면 다시 질문할 수
			있습니다.
		</div>
	);
}

function Composer({
	inputRef,
	value,
	onChange,
	onSubmit,
	onKeyDown,
	disabled,
	loading,
	canSend,
}: {
	inputRef: React.RefObject<HTMLTextAreaElement | null>;
	value: string;
	onChange: (value: string) => void;
	onSubmit: () => void;
	onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
	disabled: boolean;
	loading: boolean;
	canSend: boolean;
}) {
	const placeholder = disabled
		? "이번 세션 질문 한도에 도달했습니다. 새 탭을 열어 주세요"
		: "예: 강남구 최근 거래 5건 (Enter 전송, Shift+Enter 줄바꿈)";

	const containerClass = `flex items-end gap-2 rounded-md border bg-control px-3 py-2 transition-colors focus-within:border-brand-border ${
		disabled ? "cursor-not-allowed border-border-subtle opacity-60" : "border-border-default"
	}`;

	return (
		<div className="flex flex-col gap-2">
			<div className={containerClass}>
				<textarea
					ref={inputRef}
					value={value}
					onChange={(e) => onChange(e.target.value)}
					onKeyDown={onKeyDown}
					disabled={disabled}
					rows={1}
					placeholder={placeholder}
					aria-label="챗봇 메시지 입력"
					className="min-h-[36px] max-h-32 flex-1 resize-none bg-transparent text-sm leading-relaxed text-primary placeholder:text-quaternary focus:outline-none disabled:cursor-not-allowed"
				/>
				<button
					type="button"
					onClick={onSubmit}
					disabled={!canSend}
					aria-label="전송"
					className="shrink-0 rounded-md bg-brand px-4 py-2 text-xs font-medium text-primary transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-border disabled:cursor-not-allowed disabled:opacity-50"
				>
					{loading ? "전송 중" : "전송"}
				</button>
			</div>
		</div>
	);
}
