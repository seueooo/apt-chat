export default function Home() {
	return (
		<div className="flex h-full min-h-screen flex-col md:flex-row">
			{/* Simulator Panel */}
			<section className="flex flex-1 flex-col border-b border-border-default p-6 md:border-r md:border-b-0">
				<h2 className="mb-4 text-xl font-semibold tracking-[-0.24px] text-primary">시뮬레이터</h2>
				<div className="flex flex-1 items-center justify-center rounded-lg border border-border-subtle bg-control p-8">
					<p className="text-sm text-tertiary">시뮬레이터가 여기에 표시됩니다</p>
				</div>
			</section>

			{/* Chat Panel */}
			<section className="flex flex-1 flex-col p-6">
				<h2 className="mb-4 text-xl font-semibold tracking-[-0.24px] text-primary">AI 챗봇</h2>
				<div className="flex flex-1 items-center justify-center rounded-lg border border-border-subtle bg-control p-8">
					<p className="text-sm text-tertiary">챗봇이 여기에 표시됩니다</p>
				</div>
			</section>
		</div>
	);
}
