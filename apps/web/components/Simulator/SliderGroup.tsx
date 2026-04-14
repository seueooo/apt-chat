"use client";

/**
 * SliderGroup — 연봉/저축/대출기간 세 개의 기본 슬라이더.
 *
 * presentation only. 상위 (container) 가 `useSimulator` 의 `state`/`update` 를
 * 그대로 내려준다. 슬라이더는 native `<input type="range">` 를 Tailwind v4
 * 토큰으로 커스터마이즈 — 외부 UI 라이브러리 없음.
 */

import { formatPrice } from "@/utils/format";

type SliderGroupProps = {
	salary: number;
	savings: number;
	loanYears: number;
	onChangeSalary: (value: number) => void;
	onChangeSavings: (value: number) => void;
	onChangeLoanYears: (value: number) => void;
};

type SliderRowProps = {
	id: string;
	label: string;
	display: string;
	caption?: string;
	min: number;
	max: number;
	step: number;
	value: number;
	onChange: (value: number) => void;
};

function SliderRow({
	id,
	label,
	display,
	caption,
	min,
	max,
	step,
	value,
	onChange,
}: SliderRowProps) {
	const percent = ((value - min) / (max - min)) * 100;

	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-baseline justify-between gap-4">
				<label
					htmlFor={id}
					className="text-[13px] font-medium tracking-[-0.13px] text-tertiary uppercase"
				>
					{label}
				</label>
				<div className="flex items-baseline gap-2">
					<span className="text-lg font-medium tracking-[-0.24px] text-primary tabular-nums">
						{display}
					</span>
					{caption ? <span className="text-xs text-quaternary">{caption}</span> : null}
				</div>
			</div>
			<input
				id={id}
				type="range"
				min={min}
				max={max}
				step={step}
				value={value}
				onChange={(event) => onChange(Number(event.target.value))}
				aria-label={label}
				className="simulator-range"
				style={{ "--range-progress": `${percent}%` } as React.CSSProperties}
			/>
			<div className="flex items-center justify-between text-[11px] font-medium text-quaternary tabular-nums">
				<span>{formatRangeLabel(id, min)}</span>
				<span>{formatRangeLabel(id, max)}</span>
			</div>
		</div>
	);
}

function formatRangeLabel(id: string, value: number): string {
	if (id === "sim-loan-years") {
		return `${value}년`;
	}
	return formatPrice(value);
}

export function SliderGroup({
	salary,
	savings,
	loanYears,
	onChangeSalary,
	onChangeSavings,
	onChangeLoanYears,
}: SliderGroupProps) {
	return (
		<div className="flex flex-col gap-4">
			<SliderRow
				id="sim-salary"
				label="연봉"
				display={formatPrice(salary)}
				min={2000}
				max={50000}
				step={500}
				value={salary}
				onChange={onChangeSalary}
			/>
			<SliderRow
				id="sim-savings"
				label="저축"
				display={formatPrice(savings)}
				min={0}
				max={50000}
				step={500}
				value={savings}
				onChange={onChangeSavings}
			/>
			<SliderRow
				id="sim-loan-years"
				label="대출 기간"
				display={`${loanYears}년`}
				caption="원리금 균등상환"
				min={10}
				max={40}
				step={1}
				value={loanYears}
				onChange={onChangeLoanYears}
			/>
		</div>
	);
}
