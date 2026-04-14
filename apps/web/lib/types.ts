// 백엔드 FastAPI Pydantic 모델과 1:1 매칭. 필드 변경 시 `apps/server/routers/*.py` 와 함께 갱신.

export type SimulateRequest = {
	salary: number;
	savings: number;
	loan_years: number;
	region?: string;
	interest_rate?: number;
	dsr_limit?: number;
};

export type Apartment = {
	apartment_name: string;
	sigungu: string;
	dong: string;
	exclusive_area: number;
	floor: number;
	price: number;
	deal_date: string;
	margin: number;
};

export type SimulateResponse = {
	max_loan: number;
	monthly_payment: number;
	total_budget: number;
	affordable_count: number;
	apartments: Apartment[];
};

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
	role: ChatRole;
	content: string;
};

// 백엔드는 free-form dict 로 처리 — 시뮬레이터의 region/total_budget 등 임의 필드.
export type ChatContext = Record<string, unknown>;

export type ChatRequest = {
	messages: ChatMessage[];
	context?: ChatContext | null;
	summarize?: boolean;
};

export type VisualizationType = "line" | "bar";

export type Visualization = {
	type: VisualizationType;
	x: string;
	y: string;
};

// rows 는 backend 에서 list[list] 로 오며 컬럼 타입이 런타임 결정 → `unknown[][]`.
// 사용처에서 `columns` 와 함께 narrow 해야 한다.
export type ChatResponse = {
	answer: string;
	sql: string;
	columns: string[];
	rows: unknown[][];
	visualization: Visualization | null;
	warnings: string[];
	cache_hit: boolean;
	remaining_questions: number;
};

export type Region = {
	sigungu: string;
	dong_count: number;
	apartment_count: number;
};

export type StatsResponse = {
	total_transactions: number;
	total_apartments: number;
	date_range: {
		from: string;
		to: string;
	};
};
