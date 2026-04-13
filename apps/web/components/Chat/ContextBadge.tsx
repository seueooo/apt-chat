"use client";

/**
 * ContextBadge — 시뮬레이터 연동 컨텍스트 표시 배지.
 *
 * `useChat(context)` 로 전달되는 컨텍스트를 유저에게 시각적으로 알려주는 용도.
 * - 예산(만원 단위) 과 지역을 소문자 캡션으로 표시.
 * - 컨텍스트가 없으면 렌더하지 않음 (null 반환).
 */

import { formatPrice } from "@/utils/format";

export type ContextBadgeProps = {
	region?: string;
	budget?: number;
};

export function ContextBadge({ region, budget }: ContextBadgeProps) {
	const hasRegion = typeof region === "string" && region.length > 0;
	const hasBudget = typeof budget === "number" && Number.isFinite(budget) && budget > 0;

	if (!hasRegion && !hasBudget) {
		return null;
	}

	return (
		<div
			role="status"
			aria-label="시뮬레이터 컨텍스트"
			className="inline-flex items-center gap-2 rounded-pill border border-brand-border bg-brand-muted px-3 py-1 text-xs font-medium text-accent"
		>
			<span aria-hidden="true" className="inline-block h-1.5 w-1.5 rounded-pill bg-accent" />
			<span className="tabular-nums">
				{hasRegion ? region : null}
				{hasRegion && hasBudget ? " · " : null}
				{hasBudget ? `예산 ${formatPrice(budget as number)}` : null}
			</span>
		</div>
	);
}
