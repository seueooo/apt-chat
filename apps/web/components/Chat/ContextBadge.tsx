"use client";

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
