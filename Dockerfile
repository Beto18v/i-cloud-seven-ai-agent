# syntax=docker/dockerfile:1

# -----------------------------------------------------------------------------
# Etapa 1: Imagen binaria oficial de uv para instalación rápida y determinista
# -----------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.6.14 AS uv_bin

# -----------------------------------------------------------------------------
# Etapa 2: Builder - Construcción del entorno virtual de dependencias
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

# Copiar el binario de uv desde la etapa uv_bin
COPY --from=uv_bin /uv /uvx /bin/

# Configuración de variables de entorno para compilación y gestión de paquetes
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12

WORKDIR /app

# Copiar manifiestos de dependencias primero para optimizar la caché de capas Docker
COPY pyproject.toml uv.lock ./

# Instalar dependencias congeladas sin el paquete raíz ni dependencias de desarrollo
RUN uv sync --frozen --no-install-project --no-dev

# Copiar código fuente del proyecto y datos de referencia
COPY app/ ./app/
COPY data/ ./data/

# Instalar el proyecto en el entorno virtual
RUN uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Etapa 3: Runner - Imagen de producción mínima y ejecución no privilegiada
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runner

# Variables de entorno estándar de Python para ejecución en contenedores
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Instalar curl para la sonda de salud HEALTHCHECK y limpiar cachés del gestor de paquetes
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Crear usuario y grupo de sistema sin privilegios (appuser con UID 10001)
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g 10001 -s /bin/bash -m appuser

# Copiar el entorno virtual y los archivos de la aplicación desde el builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/app /app/app
COPY --from=builder --chown=appuser:appuser /app/data /app/data
COPY --chown=appuser:appuser pyproject.toml ./

# Inicializar y asignar permisos de directorios de trabajo para base vectorial y auditoría
RUN mkdir -p /app/data/vectorstore /app/data/audit /app/data/documents && \
    chown -R appuser:appuser /app/data

# Cambiar al usuario no-root por directiva de seguridad
USER appuser

# Exponer el puerto estándar del servicio ASGI
EXPOSE 8000

# Sonda de salud periódica sobre el endpoint /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando de arranque del servidor ASGI Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
