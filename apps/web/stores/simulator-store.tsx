"use client";

/**
 * Selector 작성 규칙 — `useSyncExternalStore` 는 `Object.is` 비교를 쓰므로
 * selector 는 primitive 또는 store 안의 안정적인 reference 만 반환해야 한다.
 *   OK   `(s) => s.salary`
 *   OK   `(s) => s.result?.apartments`  (fetch 후에만 변경되는 array ref)
 *   BAD  `(s) => ({ a: s.a, b: s.b })`  (매번 새 객체 → 무한 리렌더)
 *   BAD  `(s) => s.x ?? []`             (매번 새 배열 → 무한 리렌더; 모듈 const 로 우회)
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

const StoreContext = createContext<SimulatorStore | null>(null);

export function SimulatorStoreProvider({
	initialResult,
	children,
}: {
	initialResult: SimulateResponse | null;
	children: React.ReactNode;
}) {
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

export function useSimulatorSelector<T>(selector: (snapshot: SimulatorSnapshot) => T): T {
	const store = useStore();
	return useSyncExternalStore(
		store.subscribe,
		() => selector(store.getSnapshot()),
		() => selector(store.getSnapshot()),
	);
}

/** setter reference 는 store lifetime 동안 불변 → 호출 컴포넌트는 구독되지 않음. */
export function useSimulatorActions(): SimulatorActions {
	return useStore();
}

/**
 * Store 참조만 돌려준다 — 렌더 타임 구독 없이 이벤트 시점에 `getSnapshot()` 으로 읽기용.
 */
export function useSimulatorStoreRef(): SimulatorStore {
	return useStore();
}
