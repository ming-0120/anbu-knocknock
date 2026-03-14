export function calcLivingAlonePeriod(livingAloneSince?: string | null): {
  years: number;
  months: number;
  days: number;
} | null {
  if (!livingAloneSince) return null;

  // living_alone_since: "2020-03-01" 형태라고 가정 (서버가 DATE를 ISO로 내려주는 일반 케이스)
  const start = new Date(livingAloneSince);
  if (Number.isNaN(start.getTime())) return null;

  const today = new Date();

  // 연/월/일 차이 계산 (단순하고 예측 가능한 방식)
  let years = today.getFullYear() - start.getFullYear();
  let months = today.getMonth() - start.getMonth();
  let days = today.getDate() - start.getDate();

  // days가 음수면, 지난 달에서 일수를 빌려옴
  if (days < 0) {
    // 지난 달의 마지막 날짜
    const prevMonthLastDay = new Date(today.getFullYear(), today.getMonth(), 0).getDate();
    days += prevMonthLastDay;
    months -= 1;
  }

  // months가 음수면, 1년에서 12개월 빌려옴
  if (months < 0) {
    months += 12;
    years -= 1;
  }

  // start가 미래면 방어
  if (years < 0) return null;

  return { years, months, days };
}

export function formatLivingAlonePeriod(livingAloneSince?: string | null): string {
  const p = calcLivingAlonePeriod(livingAloneSince);
  if (!p) return "-";
  const { years, months } = p;

  // 표시용: "6년 0개월" 같은 형태
  return `${years}년 ${months}개월`;
}