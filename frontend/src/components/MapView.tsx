import { useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import { geoCentroid } from "d3-geo";

export type MapData = {
  gu: string;
  high_risk_count: number;
  max_risk_score: number;
};

type Props = {
  onGuClick: (name: string) => void;
  mapData?: MapData[];
};

const MapView = ({ onGuClick, mapData = [] }: Props) => {
  const [selectedGu, setSelectedGu] = useState<string | null>(null);
  const [hoveredGu, setHoveredGu] = useState<MapData | { gu: string } | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const COLORS = {
    bg: "#F8F9FA",
    base: "#F3F4F6", // 데이터 없을 때 연한 회색
    selectedStroke: "#1E3A8A", // 🔥 선택 시 굵게 표시할 다크 네이비 테두리
    hoverStroke: "#60A5FA",    // 🔥 마우스 호버 시 표시할 밝은 파란색 테두리
    riskHighRGB: "37, 99, 235", // 블루 스케일 (위험도 베이스 컬러)
    stroke: "#ffffff",         // 기본 흰색 얇은 테두리
    label: "#1F2937"
  };

  const { dataMap, minCount, maxCount } = useMemo(() => {
    const map = (mapData || []).reduce((acc, curr) => {
      acc[curr.gu] = curr;
      return acc;
    }, {} as Record<string, MapData>);

    const counts = (mapData || []).map((d) => d.high_risk_count || 0);
    const min = counts.length > 0 ? Math.min(...counts) : 0;
    const max = counts.length > 0 ? Math.max(...counts) : 100;

    return { dataMap: map, minCount: min, maxCount: max };
  }, [mapData]);

  // 💡 선택 여부와 상관없이 무조건 원래의 데이터(농도) 색상을 반환하도록 수정
  const getFill = (guName: string) => {
    const guData = dataMap[guName];
    if (!guData || typeof guData.high_risk_count !== "number" || guData.high_risk_count === 0) {
      return COLORS.base;
    }

    const range = maxCount - minCount === 0 ? 1 : maxCount - minCount;
    const ratio = (guData.high_risk_count - minCount) / range;
    const opacity = 0.2 + ratio * 0.7;

    return `rgba(${COLORS.riskHighRGB}, ${opacity})`; 
  };

  const centroidOverrides = useMemo(() => {
    return new Map<string, [number, number]>([
      ["양천구", [0.002, -0.007]],
      ["종로구", [0.0009, -0.01]],
      ["강남구", [0.0009, -0.01]],
      ["강북구", [0.0009, -0.01]],
      ["성북구", [0.0009, -0.01]],
      ["노원구", [0.0002, 0]],
      ["서초구", [-0.02, 0]],
    ]);
  }, []);

  return (
    <main
      style={{
        flex: 1,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: COLORS.bg,
        overflow: "hidden",
        position: "relative"
      }}
      onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
    >
      <ComposableMap
        width={800}
        height={600}
        projection="geoMercator"
        projectionConfig={{ center: [126.978, 37.5665], scale: 80000 }}
        style={{ width: "auto", height: "90%", maxWidth: "100%", maxHeight: "100%" }}
      >
        <Geographies geography="/seoul.json">
          {({ geographies }) => (
            <>
              {geographies.map((geo) => {
                const name = geo.properties.name as string;
                const isSelected = selectedGu === name;

                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    onClick={() => {
                      setSelectedGu(name);
                      onGuClick(name);
                    }}
                    onMouseEnter={() => {
                      setHoveredGu(dataMap[name] || { gu: name });
                    }}
                    onMouseLeave={() => {
                      setHoveredGu(null);
                    }}
                    // 🔥 색상은 getFill로 고정하고, stroke(테두리)만 동적으로 변경
                    style={{
                      default: {
                        fill: getFill(name),
                        stroke: isSelected ? COLORS.selectedStroke : COLORS.stroke,
                        strokeWidth: isSelected ? 2.5 : 0.8,
                        outline: "none"
                      },
                      hover: {
                        fill: getFill(name),
                        stroke: isSelected ? COLORS.selectedStroke : COLORS.hoverStroke,
                        strokeWidth: isSelected ? 2.5 : 2,
                        outline: "none",
                        cursor: "pointer"
                      },
                      pressed: {
                        fill: getFill(name),
                        outline: "none"
                      }
                    }}
                  />
                );
              })}

              {geographies.map((geo) => {
                const { name } = geo.properties as { name: string };
                let centroid = geoCentroid(geo);

                const delta = centroidOverrides.get(name);
                if (delta) centroid = [centroid[0] + delta[0], centroid[1] + delta[1]];

                return (
                  <Marker key={`${geo.rsmKey}-label`} coordinates={centroid}>
                    <text
                      textAnchor="middle"
                      style={{
                        fontSize: "12px",
                        fill: COLORS.label,
                        fontWeight: "bold",
                        pointerEvents: "none"
                      }}
                    >
                      {name}
                    </text>
                  </Marker>
                );
              })}
            </>
          )}
        </Geographies>
      </ComposableMap>

      {hoveredGu && (
        <div
          style={{
            position: "fixed",
            left: mousePos.x + 15,
            top: mousePos.y + 15,
            backgroundColor: "rgba(255, 255, 255, 0.95)",
            padding: "12px 16px",
            borderRadius: "8px",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            border: "1px solid #e5e7eb",
            pointerEvents: "none",
            zIndex: 1000,
            minWidth: "160px"
          }}
        >
          <h4 style={{ margin: "0 0 8px 0", fontSize: "16px", fontWeight: "bold", color: "#111827" }}>
            {hoveredGu.gu}
          </h4>
          {'high_risk_count' in hoveredGu ? (
            <>
              <p style={{ margin: "0 0 4px 0", fontSize: "14px", color: "#4b5563" }}>
                고위험군: <strong style={{ color: `rgb(${COLORS.riskHighRGB})`, fontSize: "15px" }}>{hoveredGu.high_risk_count}</strong>명
              </p>
              {/* <p style={{ margin: "0", fontSize: "14px", color: "#4b5563" }}>
                최대 위험도: <strong>{Number(hoveredGu.max_risk_score).toFixed(4)}</strong>
              </p> */}
            </>
          ) : (
            <p style={{ margin: "0", fontSize: "14px", color: "#9CA3AF" }}>데이터 없음</p>
          )}
        </div>
      )}
    </main>
  );
};

export default MapView;