"use client";

/**
 * AptList — 시뮬레이션 결과 매물 리스트.
 *
 * 단순 스크롤 가능한 리스트. 각 행에는 단지명/위치/면적/층/가격/여유금액을
 * 표시한다. `margin` 이 음수면 warning 색으로 표시하여 시각적 경고를 준다.
 * (이론상 backend 가 예산 내 매물만 반환하지만, 방어적 스타일링으로 유지.)
 */

import type { Apartment } from "@/lib/types";
import { formatPrice, toPyeong } from "@/utils/format";

type AptListProps = {
	apartments: Apartment[];
	loading: boolean;
};

function apartmentKey(apt: Apartment): string {
	return `${apt.apartment_name}-${apt.deal_date}-${apt.floor}-${apt.exclusive_area}`;
}

function SkeletonRow() {
	return (
		<div className="flex items-center justify-between gap-4 border-b border-border-subtle px-2 py-3">
			<div className="flex flex-col gap-2">
				<div className="h-3 w-32 rounded-full bg-control-active" />
				<div className="h-2 w-24 rounded-full bg-control-active" />
			</div>
			<div className="h-3 w-20 rounded-full bg-control-active" />
		</div>
	);
}

function AptRow({ apt }: { apt: Apartment }) {
	const marginToneClass = apt.margin < 0 ? "text-warning" : "text-success";
	const marginPrefix = apt.margin >= 0 ? "+" : "";

	return (
		<li className="flex items-start justify-between gap-4 border-b border-border-subtle px-2 py-3 last:border-b-0">
			<div className="flex min-w-0 flex-col gap-1">
				<span className="truncate text-base font-medium tracking-[-0.16px] text-primary">
					{apt.apartment_name}
				</span>
				<span className="truncate text-sm text-tertiary">
					{apt.sigungu} {apt.dong}
				</span>
				<span className="text-xs text-quaternary tabular-nums">
					{apt.exclusive_area.toFixed(1)}㎡ / {toPyeong(apt.exclusive_area)}평 · {apt.floor}층
				</span>
			</div>
			<div className="flex shrink-0 flex-col items-end gap-1">
				<span className="text-base font-semibold tracking-[-0.16px] text-primary tabular-nums">
					{formatPrice(apt.price)}
				</span>
				<span className={`text-xs tabular-nums ${marginToneClass}`}>
					{marginPrefix}
					{formatPrice(apt.margin)}
				</span>
			</div>
		</li>
	);
}

export function AptList({ apartments, loading }: AptListProps) {
	if (loading && apartments.length === 0) {
		return (
			<div
				className="flex flex-col overflow-hidden rounded-lg border border-border-default bg-control"
				aria-busy="true"
			>
				{Array.from({ length: 4 }, (_, index) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholder rows
					<SkeletonRow key={`skeleton-${index}`} />
				))}
			</div>
		);
	}

	if (apartments.length === 0) {
		return (
			<div className="flex items-center justify-center rounded-lg border border-border-default bg-control px-4 py-10">
				<p className="text-sm text-tertiary">조건에 맞는 매물이 없습니다</p>
			</div>
		);
	}

	return (
		<ul
			className={`flex max-h-[480px] flex-col overflow-y-auto rounded-lg border border-border-default bg-control transition-opacity duration-200 ${
				loading ? "opacity-70" : "opacity-100"
			}`}
			aria-busy={loading}
		>
			{apartments.map((apt) => (
				<AptRow key={apartmentKey(apt)} apt={apt} />
			))}
		</ul>
	);
}
