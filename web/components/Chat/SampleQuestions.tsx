"use client";

/**
 * SampleQuestions — 초기 상태에서 노출되는 5개 예시 질문 버튼.
 *
 * - 메시지가 없을 때만 노출 (상위 ChatWindow 가 제어).
 * - `disabled` 시 전체 버튼 비활성 (세션 소진 시).
 * - 버튼 클릭 → 부모의 `onSelect(content)` 호출 → 부모가 `useChat.send` 호출.
 */

type SampleQuestionsProps = {
	onSelect: (question: string) => void;
	disabled?: boolean;
};

const SAMPLES: readonly string[] = [
	"강남구 최근 거래 5건 보여줘",
	"서울 구별 평균 가격을 비교해줘",
	"강남구 월별 가격 추이 알려줘",
	"5억 이하 강북구 매물 있어?",
	"송파구에서 가장 비싼 아파트 TOP 5",
];

export function SampleQuestions({ onSelect, disabled = false }: SampleQuestionsProps) {
	return (
		<div className="flex flex-col gap-3">
			<span className="text-[11px] font-medium uppercase tracking-[0.08em] text-quaternary">
				예시 질문
			</span>
			<div className="flex flex-wrap gap-2">
				{SAMPLES.map((q) => (
					<button
						key={q}
						type="button"
						disabled={disabled}
						onClick={() => onSelect(q)}
						className="rounded-pill border border-border-default bg-control px-3 py-1.5 text-xs font-medium text-secondary transition-colors hover:bg-control-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-border disabled:cursor-not-allowed disabled:opacity-50"
					>
						{q}
					</button>
				))}
			</div>
		</div>
	);
}
