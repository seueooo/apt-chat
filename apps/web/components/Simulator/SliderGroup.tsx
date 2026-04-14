"use client";

import { useSimulatorActions, useSimulatorSelector } from "@/stores/simulator-store";
import { formatPrice } from "@/utils/format";

type SliderRowProps = {
	id: string;
	label: string;
	display: string;
	caption?: string;
	rangeNote?: string;
	min: number;
	max: number;
	step: number;
	value: number;
	formatBoundary: (value: number) => string;
	onChange: (value: number) => void;
};

function SliderRow({
	id,
	label,
	display,
	caption,
	rangeNote,
	min,
	max,
	step,
	value,
	formatBoundary,
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
					{caption ? <span className="text-xs text-quaternary">{caption}</span> : null}
					<span className="text-lg font-medium tracking-[-0.24px] text-primary tabular-nums">
						{display}
					</span>
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
			<div className="flex items-center justify-between gap-3 text-[11px] font-medium text-quaternary tabular-nums">
				<span>{formatBoundary(min)}</span>
				{rangeNote ? <span className="whitespace-nowrap">{rangeNote}</span> : null}
				<span>{formatBoundary(max)}</span>
			</div>
		</div>
	);
}

const formatYears = (value: number): string => `${value}년`;

function SalarySlider() {
	const salary = useSimulatorSelector((s) => s.salary);
	const { setSalary } = useSimulatorActions();
	return (
		<SliderRow
			id="sim-salary"
			label="연봉"
			display={formatPrice(salary)}
			min={2000}
			max={50000}
			step={500}
			value={salary}
			formatBoundary={formatPrice}
			onChange={setSalary}
		/>
	);
}

function SavingsSlider() {
	const savings = useSimulatorSelector((s) => s.savings);
	const { setSavings } = useSimulatorActions();
	return (
		<SliderRow
			id="sim-savings"
			label="보유 현금"
			display={formatPrice(savings)}
			min={0}
			max={50000}
			step={500}
			value={savings}
			formatBoundary={formatPrice}
			onChange={setSavings}
		/>
	);
}

function LoanYearsSlider() {
	const loanYears = useSimulatorSelector((s) => s.loanYears);
	const { setLoanYears } = useSimulatorActions();
	return (
		<SliderRow
			id="sim-loan-years"
			label="대출 기간"
			display={formatYears(loanYears)}
			caption="원리금 균등상환"
			rangeNote="한국 주담대 표준 만기"
			min={10}
			max={40}
			step={1}
			value={loanYears}
			formatBoundary={formatYears}
			onChange={setLoanYears}
		/>
	);
}

export function SliderGroup() {
	return (
		<div className="flex flex-col gap-4">
			<SalarySlider />
			<SavingsSlider />
			<LoanYearsSlider />
		</div>
	);
}
