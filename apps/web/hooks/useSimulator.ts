"use client";

/**
 * useSimulator — 시뮬레이터 상태 + 디바운스된 TanStack Query 호출.
 *
 * - 로컬 상태는 즉시 갱신 (슬라이더가 부드럽게 반응).
 * - debounced 상태가 300ms 후 따라잡으면 `api.simulate()` 쿼리가 새로 실행.
 * - 반환 시그니처는 plan 고정: `{ state, update, result, loading, error }`.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { type ApiError, api } from "@/lib/api";
import {
	DEFAULT_SIMULATOR_STATE,
	type SimulatorState,
	stateToSimulateRequest,
} from "@/lib/simulator";
import type { SimulateResponse } from "@/lib/types";

export { DEFAULT_SIMULATOR_STATE, type SimulatorState };

const DEBOUNCE_MS = 300;

export type UseSimulatorResult = {
	state: SimulatorState;
	update: <K extends keyof SimulatorState>(key: K, value: SimulatorState[K]) => void;
	result: SimulateResponse | null;
	loading: boolean;
	error: ApiError | null;
};

/**
 * @param initialResult Server Component 가 `DEFAULT_SIMULATOR_STATE` 에 대해 prefetch 한
 *   결과. 존재하면 React Query 의 `initialData` 로 주입되어 첫 렌더가 skeleton 없이 완료된다.
 *   null 이면 (backend 장애 등) 기존 클라 쿼리 플로우로 자연 fallback.
 */
export function useSimulator(initialResult?: SimulateResponse | null): UseSimulatorResult {
	const [state, setState] = useState<SimulatorState>(DEFAULT_SIMULATOR_STATE);
	const [debounced, setDebounced] = useState<SimulatorState>(DEFAULT_SIMULATOR_STATE);

	useEffect(() => {
		const id = setTimeout(() => setDebounced(state), DEBOUNCE_MS);
		return () => clearTimeout(id);
	}, [state]);

	const query = useQuery<SimulateResponse, ApiError>({
		queryKey: ["simulate", debounced],
		queryFn: () => api.simulate(stateToSimulateRequest(debounced)),
		staleTime: 60_000,
		placeholderData: (previous) => previous,
		// initialData 는 첫 쿼리 키 (=DEFAULT_SIMULATOR_STATE) 에만 적용된다.
		// 사용자가 값 변경 후 다시 기본값으로 돌아와도 해당 키는 이미 캐시되어 있으므로
		// initialData 가 재적용되지 않아 stale 데이터 오염 걱정 없음.
		initialData: initialResult ?? undefined,
	});

	const update = <K extends keyof SimulatorState>(key: K, value: SimulatorState[K]): void => {
		setState((prev) => ({ ...prev, [key]: value }));
	};

	return {
		state,
		update,
		result: query.data ?? null,
		loading: query.isPending || query.isFetching,
		error: query.error ?? null,
	};
}
