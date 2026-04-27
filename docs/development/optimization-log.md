# Optimization Log

최적화 트러블슈팅 기록. 새 엔트리는 **상단에 추가** (최신순).

엔트리 형식:

- **문제** — 무엇이 느리거나 잘못됐는가
- **원인** — 왜 그런 동작이 나왔는가
- **기존 방식** — 수정 전 코드/접근
- **수정 방식** — 수정 후 코드/접근
- **결과** — 측정치 또는 관찰된 변화
- **함정** _(있는 경우만)_ — 시도했다가 버린 대안과 이유

---

## 2026-04-14 — Simulator 전역 리렌더 → atomic store + selector 구독

### 문제

하나의 슬라이더 값이 바뀌면 페이지의 모든 ui 요소들이 리렌더링되던 상황.

### 원인

`useSimulator()` 훅이 단일 객체 (`{ state, result, loading, error, setSalary, ... }`) 를 반환하고, `Dashboard` 가 이 객체를 구독해 자식들에 prop 으로 drill 했다. `useState` 기반이라 한 필드만 바뀌어도 object reference 가 새로 생성 → Dashboard 리렌더 → 모든 자식 cascade.

```tsx
// 기존: hooks/useSimulator.ts
export function useSimulator(initialResult) {
  const [state, setState] = useState(DEFAULT_SIMULATOR_STATE);
  const [debounced, setDebounced] = useState(state);
  // ... debounce effect
  const query = useQuery({ queryKey: ["simulate", debounced], ... });
  return {
    state, setState,
    result: query.data, loading: query.isFetching, error: query.error,
    setSalary: (v) => setState((s) => ({ ...s, salary: v })),
    // ...
  };
}

// 기존: Dashboard.tsx
export function Dashboard({ initialRegions, initialResult }) {
  const sim = useSimulator(initialResult); // ← 여기 구독
  return (
    <>
      <RegionSelector value={sim.state.region} onChange={sim.setRegion} ... />
      <SliderGroup state={sim.state} onChange={...} />
      <SummaryCards result={sim.result} loading={sim.loading} />
      <AptList apartments={sim.result?.apartments ?? []} loading={sim.loading} />
      <ChatWindow context={{ region: sim.state.region, total_budget: sim.result?.total_budget }} />
    </>
  );
}
```

### 수정 방식

1. **store 방식 변경**: `stores/simulator-store.tsx` 에 `useSyncExternalStore` 기반 store 생성. 내부 `snapshot` 을 `let` 으로 들고 listener set 으로 broadcast.
2. **Action hook 분리**: `useSimulatorActions()` 는 setter 묶음만 반환 — setter reference 는 store lifetime 동안 불변이므로 이 hook 은 **listener 를 등록하지 않는다** (구독 0). 버튼/슬라이더 change 핸들러에 붙여도 리렌더 트리거 없음.
3. **컴포넌트 원자화**: `SliderGroup` 을 `SalarySlider` / `SavingsSlider` / `LoanYearsSlider` 로 쪼개 각자 자기 필드만 구독. `AdvancedSettings` 헤더의 인라인 값도 `HeaderInterestRate` / `HeaderDsrLimit` 로 분리해 헤더 텍스트만 갱신.

```tsx
// stores/simulator-store.tsx (발췌)
function createSimulatorStore(initialResult) {
  let snapshot = {
    ...DEFAULT_SIMULATOR_STATE,
    result: initialResult,
    loading: false,
    error: null,
  };
  const listeners = new Set();
  let timer;

  const emit = () => {
    for (const l of listeners) l();
  };
  const update = (patch) => {
    snapshot = { ...snapshot, ...patch };
    emit();
  };

  const scheduleQuery = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(async () => {
      update({ loading: true, error: null });
      try {
        const result = await api.simulate(stateToSimulateRequest(snapshot));
        update({ result, loading: false });
      } catch (err) {
        update({ error: err, loading: false });
      }
    }, 300);
  };

  const setField = (key) => (value) => {
    update({ [key]: value });
    scheduleQuery();
  };

  return {
    getSnapshot: () => snapshot,
    subscribe: (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    setSalary: setField("salary"),
    // ...
  };
}

export function useSimulatorSelector(selector) {
  const store = useStore();
  return useSyncExternalStore(
    store.subscribe,
    () => selector(store.getSnapshot()),
    () => selector(store.getSnapshot()),
  );
}

export function useSimulatorActions() {
  return useStore(); // setter reference 는 stable → 구독 안 됨
}

export function useSimulatorStoreRef() {
  return useStore(); // render-time 구독 없이 snapshot 직접 읽기용
}
```

```tsx
// components/Simulator/SliderGroup.tsx — atomic field
function SalarySlider() {
  const salary = useSimulatorSelector((s) => s.salary);
  const { setSalary } = useSimulatorActions();
  return <SliderRow value={salary} onChange={setSalary} ... />;
}

// components/Chat/ChatWindow.tsx — store ref only
export function ChatWindow() {
  const storeRef = useSimulatorStoreRef(); // 구독 0
  const { send, ... } = useChat();

  const handleSend = () => {
    send(input, snapshotToContext(storeRef.getSnapshot())); // 전송 순간에만 읽음
  };
  // ...
}
```

### 결과

- 드래그 중 리렌더 **1개 컴포넌트** (`SalarySlider`) 로 축소. Radix Select Provider 트리는 0회 재평가.
- Debounce 로 `api.simulate` 는 슬라이더 놓고 300ms 후 1회 → `SummaryCards` / `AptList` 가 그때 한 번만 갱신.
- Chat 파이프라인은 시뮬레이터 변화와 분리된다. 시뮬레이터 드래그 중 `ChatWindow` 의 textarea 상태는 리렌더 없이 유지됨.

### 함정

#### ① Selector 가 매번 새 참조를 반환하면 무한 리렌더

`useSyncExternalStore` 는 `Object.is` 비교라 selector 결과가 reference equal 해야 한다. 다음은 전부 무한 리렌더 함정:

```tsx
// BAD
useSimulatorSelector((s) => ({ a: s.a, b: s.b })); // 매번 새 객체
useSimulatorSelector((s) => s.result?.apartments ?? []); // 매번 새 빈 배열
```

해결: 모듈 레벨 `const EMPTY_APARTMENTS = []` 로 fallback 을 고정하거나, 필요한 slice 들을 **각각 따로** 구독.

```tsx
// GOOD
const EMPTY_APARTMENTS: Apartment[] = [];
const apartments = useSimulatorSelector(
  (s) => s.result?.apartments ?? EMPTY_APARTMENTS,
);
```

#### ② Zustand 를 쓸까 고민했다 — vanilla 로 결정

처음엔 Zustand 도입을 검토. 현재 요구 (atomic selector + stable setter + 내부 debounce) 는 `useSyncExternalStore` 한 번 감싸는 수준으로 충분했고, 런타임 의존성을 늘리지 않으려 vanilla 로 진행. 향후 middleware (persist, devtools, subscribe-with-selector) 가 필요해지면 전환 검토.

#### ③ `ChatWindow` 에서 selector 로 context 를 구독하던 초기 버전

`useChat(context)` hook 파라미터로 context 를 받고, ChatWindow 가 `useSimulatorSelector` 로 region/budget 을 구독해 prop 으로 넘기는 방식을 먼저 시도. 이 경우 **시뮬레이터 result 가 debounce 후 도착할 때마다 ChatWindow 본체가 리렌더** 되어 textarea/mutation 상태 전부 재생성 (실질 영향은 적지만 원칙 위반).

해결: `useSimulatorStoreRef()` 로 바꾸고, `send(content, context)` 시점에만 `storeRef.getSnapshot()` 으로 snapshot 을 읽어 `snapshotToContext()` 로 조립. ChatWindow 는 render-time 구독 0, 배지 UI 만 별도 atomic 자식 `ChatContextBadge` 로 분리.

---

## 2026-04-14 — Simulator 첫 로딩: 클라 쿼리 → 서버 prefetch

### 문제

사용자가 페이지 진입 → 시뮬레이터 결과 (`SummaryCards`, `AptList`) 가 나타나기까지 **700ms+** 의 지연이 있었다. 그동안 skeleton 만 보였다.

### 원인

`useSimulator` 가 전부 클라이언트에서 돌았다.

1. 페이지 HTML 은 skeleton 상태로 SSR
2. 브라우저가 JS 를 내려받고 hydrate
3. `useState` + `useEffect` 로 `debounced` 상태가 300ms 후에야 실제 값으로 갱신
4. React Query 가 그제서야 POST `/api/simulate` 를 날린다
5. Backend 가 응답 (700ms)

이 시퀀스가 직렬이라 단계마다 지연이 쌓였다.

### 기존 방식

```tsx
// app/page.tsx
export default function Home() {
  return <Dashboard />;
}

// hooks/useSimulator.ts (발췌)
export function useSimulator() {
  const [state, setState] = useState(DEFAULT_SIMULATOR_STATE);
  const [debounced, setDebounced] = useState(DEFAULT_SIMULATOR_STATE);
  useEffect(() => {
    setTimeout(() => setDebounced(state), 300);
  }, [state]);

  const query = useQuery({
    queryKey: ["simulate", debounced],
    queryFn: () => api.simulate(stateToRequest(debounced)),
    staleTime: 60_000,
    // initialData 없음 → 항상 client fetch
  });
  // ...
}
```

### 수정 방식

1. `DEFAULT_SIMULATOR_STATE` 를 `"use client"` 없는 `lib/simulator.ts` 로 분리 (SC 에서 import 가능하도록).
2. `app/page.tsx` 를 async Server Component 로 전환, `unstable_cache` 로 래핑한 `fetchDefaultSimulateCached()` 가 backend 호출.
3. `DashboardWithPrefetch` async SC 를 `Suspense` 로 감싸 fallback (loading 상태 Dashboard) 이 먼저 스트리밍되고, 실제 결과는 별도 청크로 나가게 함.
4. `useSimulator(initialResult)` 가 받은 값을 React Query `initialData` 로 주입 → 첫 렌더부터 데이터 있음.

```tsx
// app/page.tsx
const fetchDefaultSimulateCached = unstable_cache(
  async (): Promise<SimulateResponse> => {
    const res = await fetch(`${API_BASE}/api/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(stateToSimulateRequest(DEFAULT_SIMULATOR_STATE)),
    });
    if (!res.ok) throw new Error(`simulate prefetch failed: ${res.status}`);
    return (await res.json()) as SimulateResponse;
  },
  ["default-simulate-v1"],
  { revalidate: 3600, tags: ["simulate-default"] },
);

export default async function Home() {
  const regions = await fetchRegions();
  return (
    <Suspense
      fallback={<Dashboard initialRegions={regions} initialResult={null} />}
    >
      <DashboardWithPrefetch initialRegions={regions} />
    </Suspense>
  );
}

async function DashboardWithPrefetch({ initialRegions }) {
  const initialResult = await getDefaultSimulateOrNull();
  return (
    <Dashboard initialRegions={initialRegions} initialResult={initialResult} />
  );
}

// hooks/useSimulator.ts
export function useSimulator(initialResult?: SimulateResponse | null) {
  // ...
  const query = useQuery({
    queryKey: ["simulate", debounced],
    queryFn: () => api.simulate(stateToSimulateRequest(debounced)),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
    initialData: initialResult ?? undefined,
  });
  // ...
}
```

### 결과

- **Cold** (cache 비어있을 때 첫 요청): TTFB ~530ms, 실제 simulate 결과가 HTML 에 렌더된 채로 도착
- **Warm** (1시간 내 재방문): TTFB ~70ms, backend 호출 **0회** (`unstable_cache` 히트)
- Skeleton flash 사라짐. 첫 페인트부터 실제 결과가 박혀 나온다.

### 함정

#### ① `unstable_cache` 안에서 `null` 을 return 하면 실패도 캐시된다

첫 구현에서 `try/catch` 로 실패 시 `null` 을 return 했더니, backend 가 내려가 있던 순간의 `null` 이 1시간 memoize 되어 backend 복구 후에도 계속 `null` 만 반환했다.

→ 캐시 래퍼 안에서는 **throw**, 외부 wrapper `getDefaultSimulateOrNull` 에서만 catch 해 `null` 변환. `unstable_cache` 는 throw 를 memoize 하지 않으므로 다음 요청이 자동 재시도된다.

#### ② `HydrationBoundary` 는 썼다가 버렸다 — hydration mismatch 발생

처음엔 Tanstack Query 공식 RSC 패턴인 `HydrationBoundary + dehydrate(queryClient)` 를 시도했다. 결과:

```
+ Client
- Server
  <SummaryCards result={{...}} loading={false}>
    <div aria-busy={false} ...>   ← 클라
    <div aria-busy="true" ...>    ← 서버
      <span>3억 5335만</span>     ← 클라
      <span>—</span>               ← 서버
```

**원인**: `components/providers.tsx` 가 `useState(() => new QueryClient())` 로 context client 를 생성하는데, `DashboardWithPrefetch` 가 별도의 로컬 `QueryClient` 로 prefetch → dehydrate 한다. React 19 + RSC streaming 환경에서는 서버 렌더 타이밍에 dehydrated state 가 context client 로 제때 못 들어가서, 서버는 loading 상태로 HTML 을 찍고 클라이언트는 hydration 후 데이터로 렌더한다.

**해결**: `HydrationBoundary` 를 버리고 **prop 기반 `initialData`** 로 전환. 서버와 클라이언트가 같은 prop 을 받아 `useQuery` 에 넣으니, 양쪽 렌더 결과가 구조적으로 같음 → mismatch 없음. (코드는 위 "수정 방식" 참고.)

---

## 2026-04-14 — Regions: 클라 쿼리 → Server Component fetch

### 문제

`RegionSelector` 가 렌더되면 클라이언트에서 `GET /api/regions` 를 1회 호출. 지역 목록은 세션 내 불변인데도 매 탭/새로고침마다 왕복이 발생했고, Select 초기에 빈 상태 → 채워지는 flash 가 있었다.

### 원인

`useQuery` 가 mount 이후에만 fetch 를 시작. SSR 에서 아무것도 선로드하지 않아 클라이언트가 도맡았다.

### 기존 방식

```tsx
// components/Simulator/RegionSelector.tsx
export function RegionSelector({ value, onChange }) {
  const {
    data: regions,
    isPending,
    isError,
  } = useQuery({
    queryKey: ["regions"],
    queryFn: () => api.regions(),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const options = isPending || isError || !regions ? [] : regions;
  // ...
}
```

### 수정 방식

1. `app/page.tsx` 에서 backend `/api/regions` 직접 fetch (`next: { revalidate: 3600 }`). 프록시를 거치지 않고 서버→서버 호출.
2. 결과를 `initialRegions` prop 으로 `Dashboard` → `RegionSelector` 에 drill.
3. `RegionSelector` 는 `initialRegions.length > 0` 일 때만 `useQuery` 의 `initialData` 로 주입. 서버 결과가 빈 배열이면 클라 쿼리가 fallback 으로 복구를 시도하도록 (graceful degradation).

```tsx
// app/page.tsx
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

// components/Simulator/RegionSelector.tsx
export function RegionSelector({ value, onChange, initialRegions }) {
  const hasServerData = initialRegions.length > 0;
  const { data: regions, isError } = useQuery({
    queryKey: ["regions"],
    queryFn: () => api.regions(),
    staleTime: Number.POSITIVE_INFINITY,
    initialData: hasServerData ? initialRegions : undefined,
  });
  // ...
}
```

### 결과

- 해피 패스에서 클라이언트 fetch **0회**. 첫 렌더부터 완성된 Select 옵션 노출.
- Backend 장애 시 `[]` fallback → 클라 쿼리가 재시도 → 에러 UI.

---
