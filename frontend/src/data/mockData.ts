export const MOCK_DATA = [
  { 
    id: 1, name: "이OO", age: 82, gender: "남", gu: "노원구", risk: 0.98, 
    issue: "4시간 이상 무활동", status: "danger",
    address: "서울특별시 노원구 공릉동 00아파트 101동 202호",
    chartData: [{ n: "1", v: 10 }, { n: "2", v: 25 }, { n: "3", v: 20 }, { n: "4", v: 35 }, { n: "5", v: 40 }]
  },
  // ... 생략
];

export const MANAGERS = [
  { id: 1, name: "김철수", status: "접속중", statusColor: "#2ecc71", distance: "1.2km", work: 0 },
  { id: 2, name: "이영희", status: "미접속", statusColor: "#bdc3c7", distance: "0.8km", work: 1 },
  { id: 3, name: "박지민", status: "응답없음", statusColor: "#f1c40f", distance: "3.5km", work: 2 },
];