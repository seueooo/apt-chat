"use client";

/**
 * RegionSelector — "서울 전체" + `api.regions()` 결과를 Radix Select 로 렌더.
 *
 * - 부모가 `useSimulator` 의 `state.region` 과 `update("region", ...)` 을
 *   value/onValueChange 로 그대로 바인딩한다.
 * - 지역 목록은 `staleTime: Infinity` 로 한 번만 fetch (세션 내 불변).
 * - 로딩/에러 시 조용히 "서울 전체" 단일 옵션만 노출 — 시뮬레이터가 기본 지역으로
 *   동작하도록 graceful degradation.
 */

import * as Select from "@radix-ui/react-select";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown } from "lucide-react";
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
			<Select.Root value={value} onValueChange={onChange}>
				<label
					htmlFor="sim-region"
					className="text-[13px] font-medium tracking-[-0.13px] text-tertiary uppercase"
				>
					지역
				</label>
				<Select.Trigger
					id="sim-region"
					aria-label="지역"
					className="flex w-full items-center justify-between gap-2 rounded-md border border-border-default bg-control px-3 py-2 text-sm font-medium text-primary outline-none transition-colors hover:bg-control-hover focus-visible:border-brand-border focus-visible:ring-2 focus-visible:ring-brand-muted data-[state=open]:border-brand-border"
				>
					<Select.Value placeholder={ALL_REGIONS_LABEL} />
					<Select.Icon asChild>
						<ChevronDown className="size-4 text-quaternary" />
					</Select.Icon>
				</Select.Trigger>
				<Select.Portal>
					<Select.Content
						position="popper"
						sideOffset={4}
						className="z-50 w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-border-default bg-elevated shadow-popover"
					>
						<Select.Viewport className="max-h-[320px] overflow-y-auto p-1">
							<RegionItem value={ALL_REGIONS_LABEL}>{ALL_REGIONS_LABEL}</RegionItem>
							{options.map((region) => (
								<RegionItem key={region.sigungu} value={region.sigungu}>
									{region.sigungu}
								</RegionItem>
							))}
						</Select.Viewport>
					</Select.Content>
				</Select.Portal>
			</Select.Root>
			{isError ? (
				<span className="text-[11px] text-warning">지역 목록을 불러올 수 없습니다</span>
			) : null}
		</div>
	);
}

function RegionItem({ value, children }: { value: string; children: React.ReactNode }) {
	return (
		<Select.Item
			value={value}
			className="relative flex cursor-pointer select-none items-center rounded-sm py-1.5 pr-8 pl-3 text-sm text-secondary outline-none transition-colors data-[highlighted]:bg-control-hover data-[highlighted]:text-primary data-[state=checked]:text-primary"
		>
			<Select.ItemText>{children}</Select.ItemText>
			<Select.ItemIndicator className="absolute right-2 inline-flex items-center">
				<Check className="size-4 text-accent" />
			</Select.ItemIndicator>
		</Select.Item>
	);
}
