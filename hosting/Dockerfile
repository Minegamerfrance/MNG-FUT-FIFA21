FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    LOCALAPPDATA=/state/cache \
    LOCALFUT_RUNTIME_ROOT=/state/runtime \
    LOCALFUT21_USER_CONFIG_ROOT=/state/config
WORKDIR /app
COPY server/runtime-source/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && groupadd --gid 10001 mng && useradd --uid 10001 --gid mng mng \
    && mkdir -p /state && chown mng:mng /state
COPY --chown=mng:mng server/runtime-source/localfut21/ /app/localfut21/
COPY --chown=mng:mng hosting/healthcheck.py /app/healthcheck.py
COPY --chown=mng:mng hosting/account_gateway.py /app/account_gateway.py
COPY --chown=mng:mng server/runtime-source/account_transport.py /app/account_transport.py
USER 10001:10001
VOLUME ["/state"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 CMD ["python", "/app/healthcheck.py"]
CMD ["python", "-u", "/app/localfut21/server.py", "--host", "0.0.0.0", "--lsx-mode", "off"]
