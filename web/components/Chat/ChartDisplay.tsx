"use client";

/**
 * ChartDisplay — Recharts 기반 라인/바 차트 렌더.
 *
 * - `visualization` prop 의 `type` 에 따라 LineChart / BarChart 선택.
 * - `columns` + `rows` → `{ [colName]: value }[]` 형태의 Recharts data point 배열로 변환.
 * - 색상은 전부 CSS 변수 (`var(--color-*)`) 로 지정 — Tailwind 클래스 미적용 구간만.
 * - SSR 안전성: 부모 트리가 `"use client"` 이므로 기본 Recharts 임포트로 OK.
 */

import {
	Bar,
	BarChart,
	CartesianGrid,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import type { Visualization } from "@/lib/types";

type ChartDisplayProps = {
	visualization: Visualization;
	columns: string[];
	rows: unknown[][];
};

type ChartPoint = Record<string, string | number>;

/** 셀 값을 Recharts 가 그릴 수 있는 string | number 로 정규화. */
function toCellValue(raw: unknown): string | number {
	if (typeof raw === "number" && Number.isFinite(raw)) {
		return raw;
	}
	if (typeof raw === "string") {
		return raw;
	}
	if (raw == null) {
		return "";
	}
	return String(raw);
}

function buildChartData(columns: string[], rows: unknown[][]): ChartPoint[] {
	return rows.map((row) => {
		const point: ChartPoint = {};
		for (let i = 0; i < columns.length; i += 1) {
			point[columns[i]] = toCellValue(row[i]);
		}
		return point;
	});
}

export function ChartDisplay({ visualization, columns, rows }: ChartDisplayProps) {
	const data = buildChartData(columns, rows);

	if (data.length === 0) {
		return null;
	}

	const axisStroke = "var(--color-tertiary)";
	const gridStroke = "var(--color-border-subtle)";
	const brandStroke = "var(--color-brand)";
	const tooltipStyle: React.CSSProperties = {
		background: "var(--color-surface)",
		border: "1px solid var(--color-border-default)",
		borderRadius: "8px",
		color: "var(--color-primary)",
		fontSize: "12px",
		padding: "8px 12px",
	};
	const tooltipItemStyle: React.CSSProperties = { color: "var(--color-secondary)" };
	const tooltipLabelStyle: React.CSSProperties = { color: "var(--color-tertiary)" };

	return (
		<div
			className="mt-3 w-full rounded-lg border border-border-subtle bg-control px-2 py-3"
			role="img"
			aria-label={`${visualization.type === "line" ? "라인" : "막대"} 차트`}
		>
			<ResponsiveContainer width="100%" height={220}>
				{visualization.type === "line" ? (
					<LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
						<CartesianGrid stroke={gridStroke} vertical={false} />
						<XAxis
							dataKey={visualization.x}
							stroke={axisStroke}
							fontSize={11}
							tickLine={false}
							axisLine={{ stroke: gridStroke }}
						/>
						<YAxis
							stroke={axisStroke}
							fontSize={11}
							tickLine={false}
							axisLine={{ stroke: gridStroke }}
							width={48}
						/>
						<Tooltip
							contentStyle={tooltipStyle}
							itemStyle={tooltipItemStyle}
							labelStyle={tooltipLabelStyle}
							cursor={{ stroke: gridStroke, strokeWidth: 1 }}
						/>
						<Line
							type="monotone"
							dataKey={visualization.y}
							stroke={brandStroke}
							strokeWidth={2}
							dot={{ r: 3, fill: brandStroke, strokeWidth: 0 }}
							activeDot={{ r: 4 }}
						/>
					</LineChart>
				) : (
					<BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
						<CartesianGrid stroke={gridStroke} vertical={false} />
						<XAxis
							dataKey={visualization.x}
							stroke={axisStroke}
							fontSize={11}
							tickLine={false}
							axisLine={{ stroke: gridStroke }}
						/>
						<YAxis
							stroke={axisStroke}
							fontSize={11}
							tickLine={false}
							axisLine={{ stroke: gridStroke }}
							width={48}
						/>
						<Tooltip
							contentStyle={tooltipStyle}
							itemStyle={tooltipItemStyle}
							labelStyle={tooltipLabelStyle}
							cursor={{ fill: "var(--color-control-hover)" }}
						/>
						<Bar dataKey={visualization.y} fill={brandStroke} radius={[4, 4, 0, 0]} />
					</BarChart>
				)}
			</ResponsiveContainer>
		</div>
	);
}
