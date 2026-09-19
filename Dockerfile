# 与本地开发、CI 保持同一个 Python 版本：backend/pyproject.toml 声明 requires-python >=3.14，
# start_all 脚本与 README 也都按 3.14 走，镜像必须一致，否则「测过的解释器」与「跑的解释器」不同。
# requirements 里的原生依赖（scikit-learn / numpy / scipy / Pillow / psutil / psycopg-binary / pydantic-core）
# 均已提供 cp314 的 Linux wheel，无需在镜像内编译。
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

# UVICORN_WORKERS 用于单容器内多进程并行；进程内多 worker 共享后台任务队列，
# 领取是原子的，不会重复执行。（PID 1 必须是 uvicorn，故用 exec）
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}"]
