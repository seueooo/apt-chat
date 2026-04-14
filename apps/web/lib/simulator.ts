/**
 * Simulator 기본 상태 + 요청 변환.
 *
 * - 클라이언트 훅 (`useSimulator`) 과 Server Component (`app/page.tsx` 의 prefetch)
 *   양쪽에서 import 하므로 `"use client"` 디렉티브를 두지 않는다.
 * - 이 파일의 수정은 React Query 의 `["simulate", DEFAULT_SIMULATOR_STATE]` 쿼리 키에
 *   직접 영향을 주므로, 기본값을 바꾸면 서버 prefetch 와 클라이언트 첫 쿼리가 자동으로
 *   같은 키를 공유한다.
 */

import type { SimulateRequest } from "@/lib/types";

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
