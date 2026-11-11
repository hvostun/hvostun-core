FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libgl/libglib are required by the opencv wheels that mineru pulls in.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY req.txt .
# CPU build of torch: the PyPI wheel bundles ~3 GB of CUDA libraries this service never uses.
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r req.txt

COPY rag_server.py utils.py ./

EXPOSE 8000

# uvicorn CLI instead of `python rag_server.py`, which binds 127.0.0.1 only.
CMD ["uvicorn", "rag_server:app", "--host", "0.0.0.0", "--port", "8000"]
