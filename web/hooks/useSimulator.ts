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
import type { SimulateRequest, SimulateResponse } from "@/lib/types";

export type SimulatorState = {
	salary: number;
	savings: number;
	loanYears: number;
	region: string;
	interestRate: number;
	dsrLimit: number;
};

export const DEFAULT_SIMULATOR_STATE: SimulatorState = {
	salary: 5000,
	savings: 10000,
	loanYears: 30,
	region: "서울 전체",
	interestRate: 3.9,
	dsrLimit: 40,
};

const DEBOUNCE_MS = 300;

function stateToRequest(state: SimulatorState): SimulateRequest {
	return {
		salary: state.salary,
		savings: state.savings,
		loan_years: state.loanYears,
		region: state.region,
		interest_rate: state.interestRate,
		dsr_limit: state.dsrLimit,
	};
}

export type UseSimulatorResult = {
	state: SimulatorState;
	update: <K extends keyof SimulatorState>(key: K, value: SimulatorState[K]) => void;
	result: SimulateResponse | null;
	loading: boolean;
	error: ApiError | null;
};

export function useSimulator(): UseSimulatorResult {
	const [state, setState] = useState<SimulatorState>(DEFAULT_SIMULATOR_STATE);
	const [debounced, setDebounced] = useState<SimulatorState>(DEFAULT_SIMULATOR_STATE);

	useEffect(() => {
		const id = setTimeout(() => setDebounced(state), DEBOUNCE_MS);
		return () => clearTimeout(id);
	}, [state]);

	const query = useQuery<SimulateResponse, ApiError>({
		queryKey: ["simulate", debounced],
		queryFn: () => api.simulate(stateToRequest(debounced)),
		staleTime: 60_000,
		placeholderData: (previous) => previous,
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
