# 后端：FastAPI + LangGraph + MCP
#
# 关键点：MCP 服务器（playwright / filesystem）通过 `npx` 启动，因此镜像内必须带 Node.js；
# playwright 浏览器需要预装 chromium 及其系统依赖，否则运行时浏览器无法启动。

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /srv/app

# 1) 安装 Node.js 22（供运行时 `npx @playwright/mcp` / `server-filesystem` 使用）
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2) 安装 Python 依赖（复用 uv.lock，不需要重新解析）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 3) 预装 Playwright Chromium 及系统依赖（让浏览器 MCP 可用；镜像体积会明显变大）
RUN npx --yes playwright@latest install --with-deps chromium

# 4) 复制应用代码，并为运行时数据目录准备挂载点
COPY app ./app
RUN mkdir -p /srv/app/data /srv/app/sandbox

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]