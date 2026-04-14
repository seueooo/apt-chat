import { unstable_cache } from "next/cache";
import { Suspense } from "react";
import { Dashboard } from "@/components/Dashboard";
import { DEFAULT_SIMULATOR_STATE, stateToSimulateRequest } from "@/lib/simulator";
import type { Region, SimulateResponse } from "@/lib/types";

const API_BASE = process.env.API_URL || "http://localhost:8000";

/**
 * 서버에서 regions 를 선로드. 빠른 fetch 이므로 page 본문에서 await.
 * 1시간 ISR 로 backend 재호출을 줄이고, 장애 시 `[]` 반환해 graceful degradation.
 */
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

/**
 * 기본 입력값에 대한 simulate 결과를 1시간 캐시한다.
 *
 * - POST 는 Next 기본 fetch cache 대상이 아니므로 `unstable_cache` 로 래핑.
 * - 실패는 **throw** 해 null 이 memoize 되는 걸 방지. 외부 wrapper 에서 catch.
 * - 캐시 키가 default 하나뿐이라 모든 유저가 결과를 공유 → 첫 방문 이후엔 memory lookup.
 */
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

/**
 * Suspense 경계 안의 async Server Component.
 *
 * - 부모 `<Suspense>` 가 fallback Dashboard (loading 상태, skeleton) 을 스트리밍으로
 *   먼저 내보내고, 이 컴포넌트는 simulate fetch 가 끝난 후 resolve 되어 실제 결과를
 *   prop 으로 전달한다.
 * - `useSimulator` 가 prop 을 `initialData` 로 소비해 서버/클라 렌더가 동일한 HTML 을
 *   생성 → hydration mismatch 없음. (HydrationBoundary 는 중첩 QueryClient instance
 *   조합에서 RSC streaming 과 어색하게 얽혀 mismatch 를 유발하므로 의도적으로 피함.)
 */
async function DashboardWithPrefetch({ initialRegions }: { initialRegions: Region[] }) {
	const initialResult = await getDefaultSimulateOrNull();
	return <Dashboard initialRegions={initialRegions} initialResult={initialResult} />;
}
