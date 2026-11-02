# Registro de Desarrollo Asistido por IA (AI-Assisted Development Log)

Este documento detalla la metodología, gobierno y protocolos de supervisión humana aplicados durante el ciclo de vida de desarrollo asistido por Inteligencia Artificial (AI-CDL), en estricto cumplimiento de los requerimientos de la prueba técnica.

---

## 1. Herramientas Utilizadas y Entorno de Trabajo

* **Cursor IDE & Claude Code:** Utilizados como asistentes de ingeniería contextual para aceleración de boilerplate, tipado estricto con Pydantic y generación de contratos OpenAPI.
* **GitHub Copilot:** Empleado para autocompletado en línea de funciones repetitivas y transformaciones de datos JSON.

---

## 2. Fases de Asistencia y Distribución del Trabajo

```text
[Arquitectura & Requisitos]  --> 100% Definición y Criterio Humano
[Scaffolding & Boilerplate]  --> 70% Asistido por IA / 30% Revisión y Refactor
[Lógica RAG & Agentic Flow] --> 40% Asistido por IA / 60% Implementación y Pruebas Humanas
[Seguridad & Guardrails]     --> 100% Validación y Auditoría Humana
```

### Tareas Específicas Apoyadas por IA:
1. **Generación de Estructuras Pydantic:** Creación rápida de modelos de validación con tipado riguroso a partir de esquemas JSON.
2. **Generación de Documentación y Docstrings:** Estandarización de documentación inline bajo estándar Google/Sphinx.
3. **Generación de Conjuntos de Datos Mock:** Creación de registros sintéticos realistas para `mock_tickets.json` y manuales de procedimientos técnicos en Markdown.
4. **Diseño Preliminar de Casos de Prueba:** Sugerencia de matrices de testing unitario para endpoints de FastAPI usando `pytest`.

---

## 3. Protocolo de Control de Calidad y Validación Humana

Para evitar el sesgo de "caja negra" y garantizar la integridad del código en producción, se aplicaron las siguientes reglas de verificación:

### A. Prevención de Alucinaciones en Librerías de IA
* **Problema detectado:** Los modelos de asistencia tienden a sugerir métodos obsoletos de LangChain (sintaxis heredada v0.1 como `RetrievalQA` o imports deprecados de `langchain.chains`).
* **Acción correctiva humana:** Se reescribió la arquitectura usando la sintaxis moderna y modular basada en **LangChain Core (Runnables, LCEL)** y **LangGraph**, garantizando código mantenible a largo plazo.

### B. Auditoría de Seguridad y Secretos
* **Principio:** Cero exposición de credenciales en código fuente o contextos de prompts.
* **Acción correctiva humana:** Se implementó `pydantic-settings` para la inyección estricta de variables de entorno, verificando que los prompts de sistema no contuvieran datos sensibles o directivas fácilmente vulnerables.

### C. Prevención de Bucles Infinitos en el Agente
* **Problema detectado:** Al generar flujos agentic, el LLM puede proponer grafos cíclicos sin condiciones claras de parada al invocar herramientas.
* **Acción correctiva humana:** Se definieron validaciones explícitas de estados finales y un límite estricto de recursión (`recursion_limit=5`) para salvaguardar costos y latencia.

---

## 4. Riesgos Identificados y Estrategias de Mitigación

| Riesgo Técnico Identificado | Impacto Potencial | Estrategia de Mitigación Aplicada |
| :--- | :--- | :--- |
| **Dependencia ciega de código generado** | Introducción de vulnerabilidades de inyección o código subóptimo en latencia. | Revisión manual línea por línea; ejecución obligatoria de linters (`flake8`, `black`) y tipado estricto (`mypy`). |
| **Fuga de contexto en respuestas RAG** | El modelo inventa respuestas coherentes pero falsas si el chunk recuperado es ambiguo. | Ingeniería de prompts defensiva: instrucción estricta de responder *"No disponible en los manuales"* ante umbrales de similitud menores a 0.70. |
| **Sobrecarga de tokens** | Ingesta de documentos completos sin filtrado, encareciendo el costo por turno. | Fragmentación controlada con `RecursiveCharacterTextSplitter` (chunk size: 600, overlap: 80). |

---

## 5. Conclusión del Ejercicio AI-Assisted
El uso de herramientas de asistencia redujo el tiempo de desarrollo en un estimado del **45%**, principalmente en tareas de scaffolding y datos mock, permitiendo concentrar el esfuerzo del ingeniero en la toma de decisiones arquitectónicas, la robustez del pipeline RAG y la confiabilidad del agente.

---

## 6. Bitácora de Ejecución (trazabilidad de comandos)

> Obligatorio según `AGENTS.md` § 5.2. Cada fila permite reconstruir qué se ejecutó, por qué y con qué resultado, incluyendo lo que **no** se ejecutó.

### 6.1 Sesión 2026-10-31 — Bootstrap del stack con uv

**Autorización:** los comandos 1, 2, 4, 5 y 6 los ejecutó el asistente con autorización explícita del Ingeniero Líder en la conversación (excepción de `AGENTS.md` § 1.1). Comprobación del entorno: `Python 3.12.7`, `uv 0.10.8`.

| # | Comando | Motivo | Resultado |
| :-: | :--- | :--- | :--- |
| 1 | `uv add "fastapi==0.162.0" ... (15 paquetes)` | Fijar dependencias de ejecución con versiones exactas verificadas contra PyPI. | 112 paquetes instalados, 0 conflictos. |
| 2 | `uv add --dev "pytest==9.2.0" ... (5 paquetes)` | Herramientas de calidad y pruebas. | 12 paquetes instalados. |
| 3 | Edición de `pyproject.toml`: `requires-python` `>=3.12` → `>=3.11` | Alinear con README/ARCHITECTURE y con el suelo real impuesto por `pydantic-settings 2.16.2`. | `uv lock` re-resuelto. |
| 4 | `uv lock` + `uv sync --frozen` | Materializar el grafo completo en `.venv`. | 128 paquetes resueltos. |
| 5 | Verificación de imports del stack (script temporal) | Probar compatibilidad **real**, no solo de resolución. | OK: chunking 600/80, `StateGraph`, `ToolNode`, `ChatOpenAI`, `OpenAIEmbeddings`, `TestClient` → 200. |
| 6 | `uv lock --check` · `uv run ruff check main.py` · `uv run pytest --collect-only` | Validar que las configuraciones de herramientas del `pyproject.toml` son válidas. | Lock al día · "All checks passed!" · "no tests collected" (aún no existen pruebas). |
| 7 | `uv export --frozen --no-dev --no-hashes ...` | Documentar el export para Docker / Azure App Service. | **NO EJECUTADO**: el Ingeniero Líder rechazó la autorización. El comando queda documentado en `docs/DEPENDENCIAS.md` § 8 y deberá validarse al construir la imagen. |
| 8 | `Remove-Item main.py` · `Move-Item ARCHITECTURE.md, AI_DEVELOPMENT_LOG.md, PRUEBA_ORIGINAL.md docs\` | Eliminar el entrypoint de ejemplo de `uv init` y alinear la documentación con el árbol declarado en el README. | Raíz con solo `AGENTS.md`, `README.md`, `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`; los tres documentos viven en `docs/`. |

### 6.2 Hallazgos técnicos de la sesión

1. **`httpx2` es requerido por `starlette 1.10.0`** para `TestClient`; llega como transitiva de `langsmith` y `huggingface-hub`, por lo que no se declara explícitamente.
2. **`uvicorn` resuelve `sys.path`** insertando `--app-dir` (default `""`, el directorio de trabajo); `uv run uvicorn app.main:app` funcionará desde la raíz. **`pytest` no lo hace**: requiere `pythonpath = ["."]` porque `tests/` no es un paquete.
3. **`numpy` se resuelve por tramos de versión de Python** (2.5.4 en 3.12, 2.4.6 en tramos superiores), por eso `uv.lock` contiene varias resoluciones. No es un conflicto.
4. **No se instala el meta-paquete `langchain`**: `langchain-core` + `langgraph` (+ `langgraph-prebuilt`) cubren el alcance y evitan las cadenas deprecadas.