from sqlalchemy import Column, String, Integer, Text, DateTime, JSON
from sqlalchemy.sql import func
from database import Base
import uuid


class Module(Base):
    __tablename__ = "modules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True, index=True)  # 所属用户
    name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf/docx/md/txt
    parsed_content = Column(JSON, nullable=True)     # 结构化模组数据
    level_min = Column(Integer, default=1)
    level_max = Column(Integer, default=5)
    recommended_party_size = Column(Integer, default=4)
    parse_status = Column(String(20), default="pending")  # pending/processing/done/failed
    parse_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
