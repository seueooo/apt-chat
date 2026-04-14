// Server Component (`app/page.tsx` prefetch) 와 client 양쪽에서 import → `"use client"` 금지.

import type { SimulateRequest } from "@/lib/types";

// simulator state 의 region 기본값 + RegionSelector 의 placeholder/첫 옵션. 불일치 시
// controlled Select 가 빈 상태로 렌더되므로 반드시 같은 상수를 공유한다.
export const ALL_REGIONS_LABEL = "서울 전체";

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
	region: ALL_REGIONS_LABEL,
	interestRate: 3.9,
	dsrLimit: 40,
};

export function stateToSimulateRequest(state: SimulatorState): SimulateRequest {
	return {
		salary: state.salary,
		savings: state.savings,
		loan_years: state.loanYears,
		region: state.region,
		interest_rate: state.interestRate,
		dsr_limit: state.dsrLimit,
	};
}
