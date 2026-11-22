FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends unzip libgl1 libglu1-mesa libxrender1 libxext6 libsm6 libx11-6 libgomp1 && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH CAD_OUTPUT_DIR=/tmp/cad-output
WORKDIR /home/user
COPY --chown=user app.zip .
RUN unzip -q app.zip && rm app.zip
WORKDIR /home/user/ai-cad-v0
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
CMD ["sh","-c","python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
