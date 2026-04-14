"use client";

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
				<section className="flex flex-1 flex-col gap-4 p-2 md:min-h-0 md:overflow-y-auto md:p-3">
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

				<section className="flex flex-1 flex-col p-2 md:min-h-0 md:overflow-hidden md:p-3">
					<ChatWindow />
				</section>
			</div>
		</SimulatorStoreProvider>
	);
}
