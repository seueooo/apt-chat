/**
 * 숫자/단위 포맷터 유틸.
 *
 * - 순수 함수만 제공. React/DOM 의존 없음.
 * - 내부 단위는 항상 "만원" (백엔드 `price`, `total_budget` 등과 일치).
 */

const MAN_PER_EOK = 10_000;
const PYEONG_DIVISOR = 3.306;

/**
 * 만원 단위 금액을 "X억 Y만" 형태의 한국어 문자열로 변환한다.
 *
 * 예시:
 *   formatPrice(45000)     → "4억 5000만"
 *   formatPrice(10000)     → "1억"
 *   formatPrice(5000)      → "5000만"
 *   formatPrice(0)         → "0만"
 *   formatPrice(-1000)     → "-1000만"
 */
export function formatPrice(manwon: number): string {
	if (!Number.isFinite(manwon)) {
		return "-";
	}

	const isNegative = manwon < 0;
	const abs = Math.abs(Math.trunc(manwon));
	const sign = isNegative ? "-" : "";

	const eok = Math.floor(abs / MAN_PER_EOK);
	const man = abs % MAN_PER_EOK;

	if (eok === 0) {
		return `${sign}${man}만`;
	}
	if (man === 0) {
		return `${sign}${eok}억`;
	}
	return `${sign}${eok}억 ${man}만`;
}

/**
 * 제곱미터를 평수로 환산한 문자열을 반환한다 (소수점 1자리).
 *
 * 예시:
 *   toPyeong(84.9) → "25.7"
 */
export function toPyeong(sqm: number): string {
	if (!Number.isFinite(sqm)) {
		return "-";
	}
	return (sqm / PYEONG_DIVISOR).toFixed(1);
}
