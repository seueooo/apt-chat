"use client";

/**
 * simulator-store — vanilla `useSyncExternalStore` 기반 시뮬레이터 상태 store.
 *
 * 설계 원칙:
 * - **Atomic 구독**: 컴포넌트는 자신이 필요한 slice 만 selector 로 구독한다.
 *   `salary` 가 바뀌어도 `result` selector 는 같은 reference 를 반환하므로
 *   `Object.is` 비교에서 동등 → 해당 컴포넌트는 리렌더되지 않는다.
 * - **Setter 는 영원히 stable**: 액션 hook 으로 분리해 이를 사용하는 컴포넌트는
 *   리렌더 트리거에서 자동으로 빠진다 (구독 자체가 없음).
 * - **debounce 는 store 내부**: setter 가 상태 mutate 후 300ms 디바운스 fetch 를
 *   스케줄. 컴포넌트는 debounce 의 존재를 모른다.
 * - **SSR 호환**: `getServerSnapshot` 이 동일 snapshot 을 반환해 서버 / 클라이언트
 *   첫 렌더가 일치한다 (page.tsx 의 `initialResult` 가 양쪽 모두에 주입됨).
 *
 * Selector 작성 규칙 — `useSyncExternalStore` 의 비교는 `Object.is` 이므로
 * **selector 는 primitive 또는 store 안의 안정적인 reference** 만 반환해야 한다.
 *   OK   `(s) => s.salary`              (number)
 *   OK   `(s) => s.result`              (객체 ref, fetch 후에만 변경)
 *   OK   `(s) => s.result?.apartments`  (배열 ref, fetch 후에만 변경)
 *   BAD  `(s) => ({ a: s.a, b: s.b })`  (매번 새 객체 — 무한 리렌더)
 *   BAD  `(s) => s.x ?? []`             (매번 새 배열 — 무한 리렌더; 모듈 const 로 우회)
 */

import { createContext, useContext, useState, useSyncExternalStore } from "react";
import { type ApiError, api } from "@/lib/api";
import {
	DEFAULT_SIMULATOR_STATE,
	type SimulatorState,
	stateToSimulateRequest,
} from "@/lib/simulator";
import type { SimulateResponse } from "@/lib/types";

const DEBOUNCE_MS = 300;

export type SimulatorSnapshot = SimulatorState & {
	result: SimulateResponse | null;
	loading: boolean;
	error: ApiError | null;
};

export type SimulatorActions = {
	setSalary: (value: number) => void;
	setSavings: (value: number) => void;
	setLoanYears: (value: number) => void;
	setRegion: (value: string) => void;
	setInterestRate: (value: number) => void;
	setDsrLimit: (value: number) => void;
};

type SimulatorStore = SimulatorActions & {
	getSnapshot: () => SimulatorSnapshot;
	subscribe: (listener: () => void) => () => void;
};

function createSimulatorStore(initialResult: SimulateResponse | null): SimulatorStore {
	let snapshot: SimulatorSnapshot = {
		...DEFAULT_SIMULATOR_STATE,
		result: initialResult,
		loading: false,
		error: null,
	};
	const listeners = new Set<() => void>();
	let timer: ReturnType<typeof setTimeout> | undefined;

	const emit = (): void => {
		for (const listener of listeners) listener();
	};

	const update = (patch: Partial<SimulatorSnapshot>): void => {
		snapshot = { ...snapshot, ...patch };
		emit();
	};

	const scheduleQuery = (): void => {
		if (timer) clearTimeout(timer);
		timer = setTimeout(async () => {
			update({ loading: true, error: null });
			try {
				const result = await api.simulate(stateToSimulateRequest(snapshot));
				update({ result, loading: false });
			} catch (err) {
				update({
					error: err instanceof Error ? (err as ApiError) : null,
					loading: false,
				});
			}
		}, DEBOUNCE_MS);
	};

	// 필드별 setter 팩토리. 한 번 만들어진 함수는 reference 가 영원히 고정되므로
	// 컴포넌트가 prop 으로 받아도 리렌더 트리거가 되지 않는다.
	const setField =
		<K extends keyof SimulatorState>(key: K) =>
		(value: SimulatorState[K]): void => {
			update({ [key]: value } as Partial<SimulatorSnapshot>);
			scheduleQuery();
		};

	return {
		getSnapshot: () => snapshot,
		subscribe: (listener) => {
			listeners.add(listener);
			return () => {
				listeners.delete(listener);
			};
		},
		setSalary: setField("salary"),
		setSavings: setField("savings"),
		setLoanYears: setField("loanYears"),
		setRegion: setField("region"),
		setInterestRate: setField("interestRate"),
		setDsrLimit: setField("dsrLimit"),
	};
}

// --- React integration ------------------------------------------------------

const StoreContext = createContext<SimulatorStore | null>(null);

export function SimulatorStoreProvider({
	initialResult,
	children,
}: {
	initialResult: SimulateResponse | null;
	children: React.ReactNode;
}) {
	// useState lazy initializer 로 컴포넌트 인스턴스당 1회만 store 생성.
	// SSR / 클라이언트 hydration 양쪽에서 동일한 initialResult 를 받으므로
	// 첫 snapshot 도 동일 → hydration mismatch 없음.
	const [store] = useState(() => createSimulatorStore(initialResult));
	return <StoreContext.Provider value={store}>{children}</StoreContext.Provider>;
}

function useStore(): SimulatorStore {
	const store = useContext(StoreContext);
	if (!store) {
		throw new Error("Simulator store hooks must be used inside <SimulatorStoreProvider>");
	}
	return store;
}

/**
 * 저장소의 일부를 구독한다. selector 가 반환하는 값은 반드시 primitive 또는
 * store 내부의 안정적인 reference 여야 한다 (파일 상단 규칙 참고).
 */
export function useSimulatorSelector<T>(selector: (snapshot: SimulatorSnapshot) => T): T {
	const store = useStore();
	return useSyncExternalStore(
		store.subscribe,
		() => selector(store.getSnapshot()),
		() => selector(store.getSnapshot()),
	);
}

/**
 * 액션 객체를 반환한다. 액션 함수의 reference 는 store 의 lifetime 동안 불변이므로
 * 이 hook 은 컴포넌트를 리렌더 listener 에 등록하지 않는다 (구독 0).
 */
export function useSimulatorActions(): SimulatorActions {
	return useStore();
}

/**
 * Store 인스턴스 자체를 반환한다. **구독 없음.**
 *
 * 용도: 렌더 타임에는 store 를 읽을 필요가 없고, 특정 이벤트 (예: chat 전송) 시점에만
 * `store.getSnapshot()` 으로 최신 값을 읽고 싶은 경우. `useSyncExternalStore` 를 우회해
 * store 변화에 리렌더되지 않는다.
 *
 * `useContext(StoreContext)` 의 value 는 Provider 수명 동안 stable 이므로 이 hook 도
 * 실질적으로 listener 를 등록하지 않는다.
 */
export function useSimulatorStoreRef(): SimulatorStore {
	return useStore();
}
