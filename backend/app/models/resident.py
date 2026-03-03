from sqlalchemy import Column, Integer, String, DateTime, func, Float
from app.db.database import Base

class Resident(Base):
    __tablename__ = "residents"

    resident_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 워크벤치 스키마에 맞춘 컬럼들
    name = Column(String(50), nullable=False)
    resident_reg_no = Column(String(14), nullable=False, unique=True, index=True) # 주민번호 (예: 020120-4)
    phone = Column(String(20), nullable=True, index=True)
    
    # 주소 관련 컬럼 세분화
    address_main = Column(String(255), nullable=True)
    zip_code = Column(String(10), nullable=True)
    address_detail = Column(String(255), nullable=True)
    
    # 위경도 및 프로필 이미지
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    profile_image_url = Column(String(255), nullable=True)

    # 생성일
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # (참고) 이전 코드에 있던 updated_at은 워크벤치 화면에 없어서 뺐습니다.
    # 만약 DB에도 추가하실 예정이라면 아래 주석을 해제해 주세요.
    # updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())