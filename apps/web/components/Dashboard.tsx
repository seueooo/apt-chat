"use client";

/**
 * Dashboard — 시뮬레이터 + 챗봇 layout shell.
 *
 * 역할: `<SimulatorStoreProvider>` 를 마운트하고 자식들을 정렬한다.
 * 자체적으로 store 를 구독하지 않으므로 mount 이후 **다시 렌더되지 않는다**.
 * 모든 상태/액션은 자식 atomic 컴포넌트들이 selector hook 으로 직접 구독.
 *
 * - Server Component `app/page.tsx` 가 `initialRegions` / `initialResult` 를
 *   prop 으로 내려준다. 두 값 모두 SSR 시 prefetch 한 결과.
 * - `initialResult` 는 store init 으로 흡수되어 useSimulatorSelector 의 초기
 *   snapshot 이 된다.
 */

import { ChatWindow } from "@/components/Chat/ChatWindow";
import { AdvancedSettings } from "@/components/Simulator/AdvancedSettings";
import { AptList } from "@/components/Simulator/AptList";
import { RegionSelector } from "@/components/Simulator/RegionSelector";
import { SliderGroup } from "@/components/Simulator/SliderGroup";
import { SummaryCards } from "@/components/Simulator/SummaryCards";
import type { Region, SimulateResponse } from "@/lib/types";
import { SimulatorStoreProvider } from "@/stores/simulator-store";

type DashboardProps = {
	initialRegions: Region[];
	initialResult: SimulateResponse | null;
};

export function Dashboard({ initialRegions, initialResult }: DashboardProps) {
	return (
		<SimulatorStoreProvider initialResult={initialResult}>
			<div className="flex min-h-screen flex-col p-3 md:h-screen md:flex-row md:p-6">
				{/* Simulator Panel */}
				<section className="flex flex-1 flex-col gap-4 p-6 md:min-h-0 md:overflow-y-auto">
					<div className="flex flex-col gap-1">
						<h2 className="text-balance text-xl font-semibold tracking-[-0.24px] text-primary">
							When-to-Buy Apartment Simulator
						</h2>
						<p className="text-sm text-tertiary">연봉으로 서울 아파트 구매 시기 유추하기</p>
					</div>
					<RegionSelector initialRegions={initialRegions} />
					<SliderGroup />
					<AdvancedSettings />
					<SummaryCards />
					<AptList />
				</section>

				{/* Chat Panel */}
				<section className="flex flex-1 flex-col md:min-h-0 md:overflow-hidden">
					<ChatWindow />
				</section>
			</div>
		</SimulatorStoreProvider>
	);
}
