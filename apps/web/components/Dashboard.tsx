"use client";

/**
 * Dashboard — 시뮬레이터 + 챗봇을 좌우(데스크톱) / 상하(모바일) 로 합성하는
 * 단일 컨테이너. 상태는 `useSimulator()` 한 곳에서만 관리하고, 결과(`result`)
 * 와 입력(`state`) 을 presentational 자식들에 그대로 분배한다.
 *
 * - Server Component 인 `app/page.tsx` 는 이 컴포넌트 하나만 렌더한다.
 * - `ChatWindow` 는 self-contained 이며 `useChat()` 을 내부에서 소유한다.
 *   여기서는 `state.region` / `result?.total_budget` 를 prop 으로 넘겨주는
 *   "context wiring" 책임만 진다.
 */

import { ChatWindow } from "@/components/Chat/ChatWindow";
import { AdvancedSettings } from "@/components/Simulator/AdvancedSettings";
import { AptList } from "@/components/Simulator/AptList";
import { RegionSelector } from "@/components/Simulator/RegionSelector";
import { SliderGroup } from "@/components/Simulator/SliderGroup";
import { SummaryCards } from "@/components/Simulator/SummaryCards";
import { useSimulator } from "@/hooks/useSimulator";
import type { ChatContext, Region, SimulateResponse } from "@/lib/types";

type DashboardProps = {
	/** Server Component 에서 미리 fetch 한 regions. RegionSelector 의 초기 데이터로 사용된다. */
	initialRegions: Region[];
	/**
	 * Server Component 에서 `DEFAULT_SIMULATOR_STATE` 로 prefetch 한 simulate 결과.
	 * useSimulator 가 `initialData` 로 소비해 첫 렌더가 skeleton 없이 완료된다.
	 * null 이면 backend 장애 fallback — 기존 클라 쿼리 플로우.
	 */
	initialResult: SimulateResponse | null;
};

export function Dashboard({ initialRegions, initialResult }: DashboardProps) {
	const { state, update, result, loading } = useSimulator(initialResult);

	// ChatContext: 지역은 계산 전부터 유효하므로 항상 포함하고,
	// total_budget 은 시뮬레이션 결과가 있을 때만 채운다.
	const chatContext: ChatContext =
		result === null
			? { region: state.region }
			: { region: state.region, total_budget: result.total_budget };

	return (
		<div className="flex min-h-screen flex-col p-3 md:h-screen md:flex-row md:p-6">
			{/* Simulator Panel */}
			<section className="flex flex-1 flex-col gap-4 p-6 md:min-h-0 md:overflow-y-auto">
				<div className="flex flex-col gap-1">
					<h2 className="text-balance text-xl font-semibold tracking-[-0.24px] text-primary">
						When-to-Buy Apartment Simulator
					</h2>
					<p className="text-sm text-tertiary">연봉으로 서울 아파트 구매 시기 유추하기</p>
				</div>
				<RegionSelector
					value={state.region}
					onChange={(region) => update("region", region)}
					initialRegions={initialRegions}
				/>
				<SliderGroup
					salary={state.salary}
					savings={state.savings}
					loanYears={state.loanYears}
					onChangeSalary={(value) => update("salary", value)}
					onChangeSavings={(value) => update("savings", value)}
					onChangeLoanYears={(value) => update("loanYears", value)}
				/>
				<AdvancedSettings
					interestRate={state.interestRate}
					dsrLimit={state.dsrLimit}
					onInterestRateChange={(value) => update("interestRate", value)}
					onDsrLimitChange={(value) => update("dsrLimit", value)}
				/>
				<SummaryCards result={result} loading={loading} />
				<AptList apartments={result?.apartments ?? []} loading={loading} />
			</section>

			{/* Chat Panel */}
			<section className="flex flex-1 flex-col md:min-h-0 md:overflow-hidden">
				<ChatWindow
					context={chatContext}
					contextRegion={state.region}
					contextBudget={result?.total_budget}
				/>
			</section>
		</div>
	);
}
