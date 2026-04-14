"use client";

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
						className="rounded-pill border border-border-default bg-control px-3 py-1.5 text-xs font-medium text-secondary transition-[background-color,color,transform] hover:bg-control-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-border active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100"
					>
						{q}
					</button>
				))}
			</div>
		</div>
	);
}
