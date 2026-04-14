"use client";

/**
 * AdvancedSettings — 기본 접힌 상태의 "고급 설정" 패널.
 *
 * 본체는 collapse 토글 (`open`) 만 자체 상태로 들고, store 구독은 없다.
 * 헤더 inline 값과 슬라이더는 atomic 자식들이 자기 필드만 selector 로 구독한다.
 */

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { useSimulatorActions, useSimulatorSelector } from "@/stores/simulator-store";

type AdvancedSliderRowProps = {
	id: string;
	label: string;
	display: string;
	min: number;
	max: number;
	step: number;
	value: number;
	onChange: (value: number) => void;
};

function AdvancedSliderRow({
	id,
	label,
	display,
	min,
	max,
	step,
	value,
	onChange,
}: AdvancedSliderRowProps) {
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
				<span className="text-base font-medium tracking-[-0.24px] text-primary tabular-nums">
					{display}
				</span>
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
		</div>
	);
}

// --- Atomic header text components -----------------------------------------

function HeaderInterestRate() {
	const interestRate = useSimulatorSelector((s) => s.interestRate);
	return <span>금리 {interestRate.toFixed(1)}%</span>;
}

function HeaderDsrLimit() {
	const dsrLimit = useSimulatorSelector((s) => s.dsrLimit);
	return <span>DSR {dsrLimit}%</span>;
}

// --- Atomic slider field components ----------------------------------------

function InterestRateField() {
	const interestRate = useSimulatorSelector((s) => s.interestRate);
	const { setInterestRate } = useSimulatorActions();
	return (
		<AdvancedSliderRow
			id="sim-interest-rate"
			label="금리"
			display={`${interestRate.toFixed(1)}%`}
			min={0}
			max={30}
			step={0.1}
			value={interestRate}
			onChange={setInterestRate}
		/>
	);
}

function DsrLimitField() {
	const dsrLimit = useSimulatorSelector((s) => s.dsrLimit);
	const { setDsrLimit } = useSimulatorActions();
	return (
		<AdvancedSliderRow
			id="sim-dsr-limit"
			label="DSR 한도"
			display={`${dsrLimit}%`}
			min={1}
			max={100}
			step={1}
			value={dsrLimit}
			onChange={setDsrLimit}
		/>
	);
}

// --- Wrapper ---------------------------------------------------------------

export function AdvancedSettings() {
	const [open, setOpen] = useState<boolean>(false);

	return (
		<div className="flex flex-col border-t border-border-subtle pt-2">
			<button
				type="button"
				onClick={() => setOpen((prev) => !prev)}
				aria-expanded={open}
				aria-controls="sim-advanced-panel"
				className="flex items-center justify-between rounded-md px-1 py-1 text-[13px] font-medium tracking-[-0.13px] text-tertiary uppercase transition-colors hover:text-secondary focus-visible:text-secondary focus-visible:outline-none"
			>
				<span>고급 설정</span>
				<span className="flex items-center gap-3 text-[11px] font-normal normal-case tabular-nums text-quaternary">
					<HeaderInterestRate />
					<HeaderDsrLimit />
					<ChevronDown
						aria-hidden="true"
						className={`size-4 text-tertiary transition-transform duration-200 ease-[cubic-bezier(0.2,0,0,1)] ${
							open ? "rotate-180" : "rotate-0"
						}`}
					/>
				</span>
			</button>
			<div
				id="sim-advanced-panel"
				inert={!open}
				aria-hidden={!open}
				className={`grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.2,0,0,1)] ${
					open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
				}`}
			>
				<div className="overflow-hidden">
					<div className="flex flex-col gap-5 pt-4">
						<InterestRateField />
						<DsrLimitField />
					</div>
				</div>
			</div>
		</div>
	);
}
