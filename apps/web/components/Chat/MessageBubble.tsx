"use client";

/**
 * MessageBubble — user/assistant 메시지 버블의 두 explicit variant.
 *
 * - `UserMessageBubble`: 우측 정렬, 단순 텍스트
 * - `AssistantMessageBubble`: 좌측 정렬, `data` 있으면 visualization/table/SQL/warnings 렌더
 *
 * 분리 이유: 두 케이스가 사실상 별개 컴포넌트(렌더 트리·로컬 state·타입 모두 다름)인데
 * 한 함수 안에서 `if (role === "user")` 로 갈리던 걸 명시 variant 로 풀어냄.
 *
 * raw text 만 렌더 — `dangerouslySetInnerHTML` 금지 (plan 규약).
 */

import { useState } from "react";
import { ChartDisplay } from "@/components/Chat/ChartDisplay";
import type { AssistantMessage } from "@/hooks/useChat";
import type { ChatResponse } from "@/lib/types";

const INLINE_TABLE_LIMIT = 20;
const TRUNCATED_PREVIEW = 5;

function formatCell(value: unknown): string {
	if (value == null) return "-";
	if (typeof value === "number") {
		return Number.isInteger(value) ? value.toLocaleString("ko-KR") : value.toFixed(2);
	}
	if (typeof value === "string") return value;
	if (typeof value === "boolean") return value ? "true" : "false";
	try {
		return JSON.stringify(value);
	} catch {
		return String(value);
	}
}

function InlineTable({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
	if (columns.length === 0 || rows.length === 0) return null;

	return (
		<div className="mt-3 overflow-x-auto rounded-lg border border-border-subtle bg-control">
			<table className="w-full border-collapse text-xs tabular-nums">
				<thead>
					<tr className="border-b border-border-subtle">
						{columns.map((col) => (
							<th key={col} scope="col" className="px-3 py-2 text-left font-medium text-tertiary">
								{col}
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{rows.map((row, rowIdx) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: row index is stable for this snapshot
						<tr key={`row-${rowIdx}`} className="border-b border-border-subtle last:border-b-0">
							{columns.map((col, colIdx) => (
								<td key={col} className="px-3 py-2 text-secondary">
									{formatCell(row[colIdx])}
								</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

function AssistantData({ data }: { data: ChatResponse }) {
	const [sqlOpen, setSqlOpen] = useState<boolean>(false);

	const totalRows = data.rows.length;
	const tableRows =
		totalRows === 0
			? []
			: totalRows <= INLINE_TABLE_LIMIT
				? data.rows
				: data.rows.slice(0, TRUNCATED_PREVIEW);
	const isTruncated = totalRows > INLINE_TABLE_LIMIT;

	return (
		<>
			{data.visualization ? (
				<ChartDisplay visualization={data.visualization} columns={data.columns} rows={data.rows} />
			) : null}

			{tableRows.length > 0 ? (
				<>
					<InlineTable columns={data.columns} rows={tableRows} />
					{isTruncated ? (
						<p className="mt-2 text-[11px] text-quaternary">
							상위 {TRUNCATED_PREVIEW}행만 표시 · 전체 {totalRows.toLocaleString("ko-KR")}행
						</p>
					) : null}
				</>
			) : null}

			{data.warnings.length > 0 ? (
				<ul className="mt-3 flex flex-col gap-1 text-[11px] text-warning">
					{data.warnings.map((w) => (
						<li key={w}>⚠ {w}</li>
					))}
				</ul>
			) : null}

			{data.sql ? (
				<div className="mt-3">
					<button
						type="button"
						onClick={() => setSqlOpen((prev) => !prev)}
						aria-expanded={sqlOpen}
						aria-controls="assistant-sql-block"
						className="inline-block origin-left text-[11px] font-medium uppercase tracking-[0.08em] text-quaternary transition-[color,transform] hover:text-tertiary focus-visible:outline-none focus-visible:text-tertiary active:scale-[0.96]"
					>
						SQL {sqlOpen ? "▴" : "▾"}
					</button>
					{sqlOpen ? (
						<pre
							id="assistant-sql-block"
							className="mt-2 overflow-x-auto rounded-md border border-border-subtle bg-canvas px-3 py-2 font-mono text-[11px] leading-relaxed text-tertiary"
						>
							<code>{data.sql}</code>
						</pre>
					) : null}
				</div>
			) : null}
		</>
	);
}

export function UserMessageBubble({ content }: { content: string }) {
	return (
		<div className="flex justify-end">
			<div className="max-w-[85%] rounded-lg border border-border-default bg-control-active px-4 py-3 text-sm leading-relaxed text-primary">
				{content}
			</div>
		</div>
	);
}

export function AssistantMessageBubble({ message }: { message: AssistantMessage }) {
	return (
		<div className="flex justify-start">
			<div className="w-full max-w-[92%] rounded-lg border border-border-subtle bg-panel px-4 py-3">
				<p className="whitespace-pre-wrap text-pretty text-sm leading-relaxed text-secondary">
					{message.content}
				</p>
				{message.data ? <AssistantData data={message.data} /> : null}
			</div>
		</div>
	);
}
