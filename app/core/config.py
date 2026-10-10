"""集中管理路径、常量与 LLM 配置。"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# 项目根目录 = 多用户ai智能助理平台/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"
SANDBOX = BASE_DIR / "sandbox"

# 两个 SQLite 库：一个给 LangGraph 检查点，一个给业务数据
CHECKPOINT_DB = DATA_DIR / "checkpoints.sqlite"
APP_DB = DATA_DIR / "app.db"

# LLM 配置（默认 glm-4.5-air，与原始 demo 保持一致）
LLM_MODEL = os.getenv("LLM_MODEL", "glm-4.5-air")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")

# 评估器最大重试次数
MAX_ATTEMPTS = 3

# 日志级别（可观测性）
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# trace / token / 成本由 LangSmith 接管：LANGSMITH_* 已在 .env 配置并经
# load_dotenv(override=True) 加载，LangChain 会自动上报，此处无需额外代码。

# JWT 认证配置
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-in-production-0123456789")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)