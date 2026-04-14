"use client";

/**
 * SummaryCards — 시뮬레이션 결과 요약 (최대 대출 / 월 상환액 / 구매 총액).
 *
 * 단위 메모: backend `loan_calculator.py` 기준 `monthly_payment` 는
 * `salary * (dsr_limit/100) / 12` (만원) — `max_loan`, `total_budget` 와
 * 동일한 "만원" 단위이므로 세 필드 모두 `formatPrice()` 를 그대로 사용한다.
 */

import type { SimulateResponse } from "@/lib/types";
import { useSimulatorSelector } from "@/stores/simulator-store";
import { formatPrice } from "@/utils/format";

type CardSpec = {
	id: "max-loan" | "monthly" | "total";
	label: string;
	value: string;
	suffix?: string;
};

function buildCards(result: SimulateResponse | null): CardSpec[] {
	if (result === null) {
		return [
			{ id: "max-loan", label: "최대 대출", value: "—" },
			{ id: "monthly", label: "월 상환액", value: "—" },
			{ id: "total", label: "구매 총액", value: "—" },
		];
	}
	return [
		{ id: "max-loan", label: "최대 대출", value: formatPrice(result.max_loan) },
		{ id: "monthly", label: "월 상환액", value: formatPrice(result.monthly_payment) },
		{ id: "total", label: "구매 총액", value: formatPrice(result.total_budget) },
	];
}

export function SummaryCards() {
	// result 객체 ref 는 fetch 후에만 변하므로 selector 가 안정적.
	// loading 도 primitive boolean.
	const result = useSimulatorSelector((s) => s.result);
	const loading = useSimulatorSelector((s) => s.loading);
	const cards = buildCards(result);
	const isStale = loading && result !== null;

	return (
		<div className="grid grid-cols-1 gap-3 sm:grid-cols-3" aria-busy={loading} aria-live="polite">
			{cards.map((card) => (
				<div
					key={card.id}
					className={`flex flex-col gap-1 rounded-lg border border-border-default bg-control p-4 transition-opacity duration-200 ${
						isStale ? "opacity-60" : "opacity-100"
					}`}
				>
					<span className="text-[11px] font-medium tracking-[-0.11px] text-tertiary uppercase">
						{card.label}
					</span>
					<span className="text-xl font-semibold tracking-[-0.24px] text-primary tabular-nums">
						{card.value}
					</span>
				</div>
			))}
		</div>
	);
}
