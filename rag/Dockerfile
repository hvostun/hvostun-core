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

# GigaChat OAuth needs НУЦ Минцифры (otherwise SSLCertVerificationError on
# ngw.devices.sberbank.ru). Kept after pip so the heavy layer stays cached.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && curl -fsSL -o /usr/local/share/ca-certificates/russian_trusted_root_ca.crt \
      https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt \
 && curl -fsSL -o /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt \
      https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt \
 && update-ca-certificates \
 && python -c "import certifi, pathlib; p=pathlib.Path(certifi.where()); \
root=pathlib.Path('/usr/local/share/ca-certificates/russian_trusted_root_ca.crt').read_text(); \
sub=pathlib.Path('/usr/local/share/ca-certificates/russian_trusted_sub_ca.crt').read_text(); \
p.write_text(p.read_text()+'\n'+root+'\n'+sub+'\n')" \
 && rm -rf /var/lib/apt/lists/*

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY rag_server.py utils.py ./

EXPOSE 8000

# uvicorn CLI instead of `python rag_server.py`, which binds 127.0.0.1 only.
CMD ["uvicorn", "rag_server:app", "--host", "0.0.0.0", "--port", "8000"]
