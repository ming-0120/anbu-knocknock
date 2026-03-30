import os, joblib, asyncio, numpy as np, pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import select
from sklearn.metrics import roc_auc_score, confusion_matrix
from app.db.database import AsyncSessionLocal
from app.models.hourly_feature import HourlyFeature
from datetime import timedelta

# ✅ PPT용 고해상도 설정
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'Malgun Gothic' # 한글 폰트
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
PLOT_DIR = os.path.join(BASE_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# 학습 시 사용한 실제 컬럼명
COLS = ["x1_motion_count", "x2_door_count", "x3_avg_interval", "x4_night_motion_count", 
        "x5_first_motion_min", "x6_last_motion_min", "is_daytime"]

async def create_comparison_report():
    async with AsyncSessionLocal() as db:
        # 비교 대상: 성공(164) vs 한계(204)
        compare_ids = [164, 300] 
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        for i, rid in enumerate(compare_ids):
            print(f"📈 [거주자 {rid}] 분석 중...")
            model = joblib.load(os.path.join(MODEL_DIR, f"resident_{rid}_model.pkl"))
            scaler = joblib.load(os.path.join(MODEL_DIR, f"resident_{rid}_scaler.pkl"))

            # 데이터 로드 및 라벨링
            stmt = select(HourlyFeature).where(HourlyFeature.resident_id == rid).order_by(HourlyFeature.target_hour)
            rows = (await db.execute(stmt)).scalars().all()
            max_hour = max(r.target_hour for r in rows)
            accident_cutoff = max_hour - timedelta(days=2) # 마지막 2일이 사고

            y_true, scores = [], []
            for r in rows:
                y_true.append(1 if r.target_hour > accident_cutoff else 0)
                df = pd.DataFrame([{
                    "x1_motion_count": float(r.x1_motion_count or 0),
                    "x2_door_count": float(r.x2_door_count or 0),
                    "x3_avg_interval": np.log1p(float(getattr(r, "x3_avg_interval", 0) or 0)),
                    "x4_night_motion_count": float(getattr(r, "x4_night_motion_count", 0) or 0),
                    "x5_first_motion_min": float(getattr(r, "x5_first_motion_min", 0) or 0),
                    "x6_last_motion_min": float(getattr(r, "x6_last_motion_min", 0) or 0),
                    "is_daytime": 1.0 if 6 <= r.target_hour.hour <= 22 else 0.0
                }])
                raw = model.decision_function(scaler.transform(df))[0]
                scores.append(0.05 - raw)

            scores, y_true = np.array(scores), np.array(y_true)
            auc = roc_auc_score(y_true, scores)
            
            # 왼쪽: 분포도 그래프 (Distribution)
            sns.kdeplot(scores[y_true==0], ax=axes[i,0], fill=True, color='#4A90E2', label='정상(28일)')
            sns.kdeplot(scores[y_true==1], ax=axes[i,0], fill=True, color='#E76F51', label='이상(2일)')
            title_type = "성공 사례" if rid == 164 else "개선 과제"
            axes[i,0].set_title(f"[{title_type}] ID {rid} 위험 점수 분포 (AUC: {auc:.3f})", fontsize=14, fontweight='bold')
            axes[i,0].legend()

            # 오른쪽: 혼동 행렬 (Confusion Matrix)
            threshold = np.percentile(scores, 93) # 상위 7%를 이상으로 가정 (2일/30일)
            cm = confusion_matrix(y_true, scores >= threshold)
            sns.heatmap(cm, annot=True, fmt='d', ax=axes[i,1], cmap='Purples', cbar=False,
                        xticklabels=['정상 예측', '이상 예측'], yticklabels=['실제 정상', '실제 이상'])
            axes[i,1].set_title(f"ID {rid} 탐지 결과 요약", fontsize=14, fontweight='bold')

        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_DIR, "ppt_final_comparison.png"), dpi=300)
        print(f"✅ PPT용 통합 리포트 저장 완료: plots/ppt_final_comparison.png")

if __name__ == "__main__":
    asyncio.run(create_comparison_report())