/**
 * apt-chat backend API 타입 정의.
 *
 * 백엔드 FastAPI Pydantic 모델과 1:1 매칭된다. 필드 추가/변경 시 반드시
 * `api/routers/*.py` 와 함께 갱신해야 한다.
 */

// --- /api/simulate -----------------------------------------------------------

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

// --- /api/chat ---------------------------------------------------------------

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
	role: ChatRole;
	content: string;
};

export type ChatRequest = {
	messages: ChatMessage[];
	context?: Record<string, unknown> | null;
	summarize?: boolean;
};

export type VisualizationType = "line" | "bar";

export type Visualization = {
	type: VisualizationType;
	x: string;
	y: string;
};

/**
 * ChatResponse.rows 는 백엔드에서 `list[list]` 로 반환되며 각 컬럼의 런타임
 * 타입이 동적으로 결정되므로 `unknown` 으로 둔다. 사용처에서 `columns` 와
 * 함께 narrowing 필요.
 */
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

// --- /api/regions & /api/stats -----------------------------------------------

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
