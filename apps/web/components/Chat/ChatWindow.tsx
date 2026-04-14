"use client";

/**
 * ChatWindow — 챗봇 메인 컨테이너.
 *
 * 중요: **시뮬레이터 store 를 구독하지 않는다.** `useSimulatorStoreRef()` 로
 * store reference 만 받아 전송 시점에만 `getSnapshot()` 으로 최신 region/budget
 * 을 읽는다. 덕분에 슬라이더 드래그/debounced result 업데이트 등 시뮬레이터 상태
 * 변화에 ChatWindow 본체는 리렌더되지 않는다.
 *
 * 배지 UI 는 별도 atomic 컴포넌트 `ChatContextBadge` 가 selector 로 자기 slice 만
 * 구독 → 시각적으로는 실시간 반영되면서도 ChatWindow 본체는 정지 상태 유지.
 *
 * - `useChat()` 훅을 통해 메시지 상태 / 낙관적 카운터 / mutation 상태를 가져온다.
 * - 메시지가 없으면 hero + SampleQuestions + ContextBadge 노출.
 * - 있으면 메시지 목록 + 입력창.
 * - 한글 IME: `e.nativeEvent.isComposing` 체크 필수.
 * - 소진(`isExhausted`) 시 입력창/샘플 버튼 모두 disabled + 경고 배너.
 */

import { useRef, useState } from "react";
import { ContextBadge } from "@/components/Chat/ContextBadge";
import { AssistantMessageBubble, UserMessageBubble } from "@/components/Chat/MessageBubble";
import { SampleQuestions } from "@/components/Chat/SampleQuestions";
import { type Message, useChat } from "@/hooks/useChat";
import { MAX_QUESTIONS_PER_SESSION } from "@/lib/session";
import type { ChatContext } from "@/lib/types";
import {
	type SimulatorSnapshot,
	useSimulatorSelector,
	useSimulatorStoreRef,
} from "@/stores/simulator-store";

function snapshotToContext(snapshot: SimulatorSnapshot): ChatContext {
	const totalBudget = snapshot.result?.total_budget;
	return totalBudget != null
		? { region: snapshot.region, total_budget: totalBudget }
		: { region: snapshot.region };
}

export function ChatWindow() {
	// Store reference 만 획득. useContext 기반이라 context value 가 stable 한 동안
	// (= Provider 의 lifetime 내내) 이 컴포넌트를 리렌더 트리거에 등록하지 않는다.
	const storeRef = useSimulatorStoreRef();

	const { messages, loading, send, remainingQuestions, isExhausted, error } = useChat();
	const [input, setInput] = useState<string>("");
	const textareaRef = useRef<HTMLTextAreaElement | null>(null);

	const canSend = !isExhausted && !loading && input.trim().length > 0;

	const handleSend = (): void => {
		if (!canSend) return;
		const value = input;
		setInput("");
		// 전송 순간 snapshot 을 읽어 최신 context 조립 — 렌더 타임 구독 없이도 정확성 유지.
		send(value, snapshotToContext(storeRef.getSnapshot()));
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
		send(question, snapshotToContext(storeRef.getSnapshot()));
		textareaRef.current?.focus();
	};

	return (
		<div className="flex h-full min-h-0 flex-col gap-4">
			<Header remainingQuestions={remainingQuestions} />

			<div className="flex min-h-0 flex-1 flex-col gap-4">
				{messages.length === 0 ? (
					<EmptyMessageList isExhausted={isExhausted} onSampleSelect={handleSampleSelect} />
				) : (
					<PopulatedMessageList messages={messages} loading={loading} />
				)}

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

function Header({ remainingQuestions }: { remainingQuestions: number }) {
	const warningThreshold = remainingQuestions <= 1;
	const badgeToneClass = warningThreshold ? "text-warning" : "text-tertiary";

	return (
		<div className="flex flex-wrap items-center justify-between gap-3">
			<div className="flex flex-wrap items-center gap-2">
				<ChatContextBadge />
			</div>
			<div
				className={`inline-flex items-center gap-1.5 rounded-pill bg-control-active px-3 py-1 text-[11px] font-medium tabular-nums ${badgeToneClass}`}
				aria-live="polite"
			>
				<span className="uppercase tracking-[0.08em]">남은 질문</span>
				<span>
					{remainingQuestions}/{MAX_QUESTIONS_PER_SESSION}
				</span>
			</div>
		</div>
	);
}

// Atomic subcomponent — simulator store 의 region/totalBudget slice 만 구독한다.
// 시뮬레이터 값이 바뀌면 **이 작은 뱃지만** 리렌더되며, ChatWindow 본체는 정지 상태.
function ChatContextBadge() {
	const region = useSimulatorSelector((s) => s.region);
	const totalBudget = useSimulatorSelector((s) => s.result?.total_budget);
	return <ContextBadge region={region} budget={totalBudget} />;
}

function EmptyMessageList({
	isExhausted,
	onSampleSelect,
}: {
	isExhausted: boolean;
	onSampleSelect: (question: string) => void;
}) {
	return (
		<div className="flex min-h-0 flex-1 flex-col justify-between gap-6 rounded-lg border border-border-subtle bg-control p-6">
			<div className="flex flex-col gap-2">
				<h3 className="text-balance text-lg font-medium tracking-[-0.24px] text-primary">
					무엇이 궁금하세요?
				</h3>
				<p className="text-pretty text-sm leading-relaxed text-tertiary">
					자연어로 질문하면 실거래가 데이터에서 바로 답을 찾아 드립니다. 차트와 표가 필요한 질문은
					자동으로 시각화됩니다.
				</p>
			</div>
			<SampleQuestions onSelect={onSampleSelect} disabled={isExhausted} />
		</div>
	);
}

function PopulatedMessageList({ messages, loading }: { messages: Message[]; loading: boolean }) {
	return (
		<div
			className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto rounded-lg border border-border-subtle bg-control p-4"
			aria-busy={loading}
			aria-live="polite"
		>
			{messages.map((msg, idx) =>
				msg.role === "user" ? (
					// biome-ignore lint/suspicious/noArrayIndexKey: messages append-only, index stable per session
					<UserMessageBubble key={`msg-${idx}`} content={msg.content} />
				) : (
					// biome-ignore lint/suspicious/noArrayIndexKey: messages append-only, index stable per session
					<AssistantMessageBubble key={`msg-${idx}`} message={msg} />
				),
			)}
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
			비용 제어를 위해 세션당 질문 수를 {MAX_QUESTIONS_PER_SESSION}회로 제한합니다. 새 탭을 열면
			다시 질문할 수 있습니다.
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
					className="shrink-0 rounded-pill bg-brand px-5 py-2 text-xs font-medium text-primary transition-[background-color,transform] hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-border active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100"
				>
					{loading ? "전송 중" : "전송"}
				</button>
			</div>
		</div>
	);
}
