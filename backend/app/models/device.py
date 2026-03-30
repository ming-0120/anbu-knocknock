from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class Device(Base):
    __tablename__ = "devices"

    device_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 외래키 설정
    resident_id = Column(Integer, ForeignKey("residents.resident_id"), nullable=False, index=True)

    # 기기 식별 정보
    device_uid = Column(String(64), nullable=False, unique=True, index=True)
    
    # 💡 추가된 컬럼들
    device_type = Column(String(20), nullable=False) # motion, door 등
    location_label = Column(String(50), nullable=True)     # 거실, 현관, 침실 등
    firmware_version = Column(String(20), nullable=True, server_default="v1.0.0")
    
    # 상태 정보
    status = Column(String(16), nullable=False, server_default="active")

    # 시간 정보
    # 마지막 활동 시간을 기록해야 기기 생존 여부나 입주민 활동을 파악하기 좋습니다.
    last_seen_at = Column(DateTime(timezone=True), nullable=True) 
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 관계 설정 (필요 시)
    # resident = relationship("Resident", back_populates="devices")