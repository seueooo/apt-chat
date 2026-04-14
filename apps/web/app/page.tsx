import { unstable_cache } from "next/cache";
import { Suspense } from "react";
import { Dashboard } from "@/components/Dashboard";
import { DEFAULT_SIMULATOR_STATE, stateToSimulateRequest } from "@/lib/simulator";
import type { Region, SimulateResponse } from "@/lib/types";

const API_BASE = process.env.API_URL || "http://localhost:8000";

// 1시간 ISR. 장애 시 `[]` 반환 → RegionSelector 가 "서울 전체" 단일 옵션으로 degrade.
async function fetchRegions(): Promise<Region[]> {
	try {
		const res = await fetch(`${API_BASE}/api/regions`, {
			next: { revalidate: 3600 },
		});
		if (!res.ok) return [];
		const data = (await res.json()) as { regions: Region[] };
		return data.regions ?? [];
	} catch {
		return [];
	}
}

// POST 는 Next 기본 fetch cache 대상이 아니라 `unstable_cache` 로 래핑.
// 실패 시 throw — `unstable_cache` 는 throw 를 memoize 하지 않으므로 다음 요청이 자동 재시도.
// null 을 return 하면 장애 순간의 null 이 1시간 박제되어 backend 복구 후에도 계속 null 이 나온다.
const fetchDefaultSimulateCached = unstable_cache(
	async (): Promise<SimulateResponse> => {
		const res = await fetch(`${API_BASE}/api/simulate`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(stateToSimulateRequest(DEFAULT_SIMULATOR_STATE)),
		});
		if (!res.ok) {
			throw new Error(`simulate prefetch failed: ${res.status}`);
		}
		return (await res.json()) as SimulateResponse;
	},
	["default-simulate-v1"],
	{ revalidate: 3600, tags: ["simulate-default"] },
);

async function getDefaultSimulateOrNull(): Promise<SimulateResponse | null> {
	try {
		return await fetchDefaultSimulateCached();
	} catch {
		return null;
	}
}

export default async function Home() {
	const regions = await fetchRegions();
	return (
		<Suspense fallback={<Dashboard initialRegions={regions} initialResult={null} />}>
			<DashboardWithPrefetch initialRegions={regions} />
		</Suspense>
	);
}

// prop 기반 initialResult → 서버/클라 렌더 HTML 구조가 동일 → hydration mismatch 없음.
// `HydrationBoundary` + dehydrate 는 중첩 QueryClient 와 RSC streaming 이 얽혀 mismatch 발생 → 회피.
async function DashboardWithPrefetch({ initialRegions }: { initialRegions: Region[] }) {
	const initialResult = await getDefaultSimulateOrNull();
	return <Dashboard initialRegions={initialRegions} initialResult={initialResult} />;
}
