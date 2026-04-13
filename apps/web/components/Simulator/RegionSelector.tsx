"use client";

/**
 * RegionSelector — "서울 전체" + `api.regions()` 결과를 native `<select>` 로 렌더.
 *
 * - 부모 컴포넌트가 `useSimulator` 의 `state.region` 과 `update("region", ...)` 을
 *   value/onChange 로 그대로 바인딩한다.
 * - 지역 목록은 `staleTime: Infinity` 로 한 번만 fetch (세션 내 불변).
 * - 로딩/에러 시 조용히 "서울 전체" 단일 옵션만 노출 — 시뮬레이터가 기본 지역으로
 *   동작하도록 graceful degradation.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Region } from "@/lib/types";

const ALL_REGIONS_LABEL = "서울 전체";

type RegionSelectorProps = {
	value: string;
	onChange: (region: string) => void;
};

export function RegionSelector({ value, onChange }: RegionSelectorProps) {
	const {
		data: regions,
		isPending,
		isError,
	} = useQuery<Region[]>({
		queryKey: ["regions"],
		queryFn: () => api.regions(),
		staleTime: Number.POSITIVE_INFINITY,
	});

	const options = isPending || isError || !regions ? [] : regions;

	return (
		<div className="flex flex-col gap-2">
			<label
				htmlFor="sim-region"
				className="text-[13px] font-medium tracking-[-0.13px] text-tertiary uppercase"
			>
				지역
			</label>
			<div className="relative">
				<select
					id="sim-region"
					value={value}
					onChange={(event) => onChange(event.target.value)}
					aria-label="지역"
					className="w-full appearance-none rounded-md border border-border-default bg-control px-3 py-2 pr-9 text-sm font-medium text-primary outline-none transition-colors hover:bg-control-hover focus-visible:border-brand-border focus-visible:ring-2 focus-visible:ring-brand-muted"
				>
					<option value={ALL_REGIONS_LABEL}>{ALL_REGIONS_LABEL}</option>
					{options.map((region) => (
						<option key={region.sigungu} value={region.sigungu}>
							{region.sigungu}
						</option>
					))}
				</select>
				<span
					aria-hidden="true"
					className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-quaternary"
				>
					▾
				</span>
			</div>
			{isError ? (
				<span className="text-[11px] text-warning">지역 목록을 불러올 수 없습니다</span>
			) : null}
		</div>
	);
}
