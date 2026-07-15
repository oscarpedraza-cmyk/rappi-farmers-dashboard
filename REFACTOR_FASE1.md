# Refactor Fase 1 — Hardening seguro

Rama: `refactor/fase-1-hardening` · Sin push a producción hasta tu validación.
Principio rector: **cero cambios de comportamiento y cero cambios visuales.**

---

## 1. Resumen ejecutivo

El proyecto estaba funcional pero sin ninguna red de seguridad automatizada, con
constantes de negocio dispersas, comentarios con encoding corrupto y errores
silenciados. La Fase 1 **no reescribe** la arquitectura: primero instala una red
de seguridad (80 tests de caracterización que congelan el comportamiento actual)
y luego aplica mejoras de bajo riesgo verificadas contra esa red.

Resultado: mismo comportamiento, misma UI, pero ahora el código tiene una única
fuente de verdad para la configuración, registro de errores real y una base de
pruebas que hará seguras las fases siguientes.

- **80/80 tests verdes** antes y después de cada cambio.
- **ruff limpio** en `config/`, `core/` y `tests/`.
- **App verificada en runtime**: bootea, login y panel de supervisor renderizan,
  sin errores de consola.

## 2. Archivos modificados

**Nuevos**
- `config/__init__.py`, `config/team.py`, `config/scoring.py`, `config/storage.py`
- `tests/__init__.py`, `tests/conftest.py`, `tests/test_metrics.py`,
  `tests/test_loader.py`, `tests/test_db.py`
- `pytest.ini`, `requirements-dev.txt`, `.claude/launch.json`, este documento.

**Modificados**
- `core/loader.py` — roster movido a `config.team` (re-exportado).
- `core/metrics.py` — pesos/bounds/umbrales movidos a `config.scoring`.
- `core/db.py` — identificadores a `config.storage`, encoding arreglado, logging.
- `core/auth.py` — identidad de supervisor y TTL desde `config`, código muerto fuera.

## 3. Explicación de cada cambio importante

- **Paquete `config/`** — Toda constante de negocio (13 farmers, Slack IDs, pesos
  de compensación 35/20/20/25, bounds 0.80–1.50, umbrales de semáforo, tabs de
  GSheet, límite de celda de 49K, TTL de sesión) vive ahora en un solo lugar. Los
  módulos `core` la importan **y la re-exportan**, por lo que todos los nombres
  públicos (`FARMERS_EMAILS`, `WEIGHTS`, `DB_PATH`, `SESSION_TTL`, …) siguen
  existiendo igual y ninguna página se rompe.
- **Encoding** — Los separadores de comentario de `db.py` estaban corruptos
  (mojibake `â"€â"€`). Reemplazados por `# ──` limpios en UTF-8. Solo comentarios.
- **Logging** — 5 helpers de Google Sheets y `_filter_excluded` registraban el
  fallo con `logger.warning` en vez de tragarlo en silencio. **Mismo valor de
  retorno** en cada caso: solo se añade visibilidad.
- **Código muerto** — Quitado `import traceback` sin uso y 6 variables locales
  muertas en `render_topbar` (no afectaban el HTML renderizado).

## 4. Problemas encontrados

| # | Hallazgo | Severidad |
|---|----------|-----------|
| 1 | Cero tests en una app de producción con auto-deploy | 🔴 Crítico |
| 2 | Comentarios con encoding corrupto en `db.py` | 🟡 |
| 3 | `except Exception: pass` / returns silenciosos que ocultan fallos de GSheets | 🟡 |
| 4 | Constantes de negocio dispersas en 4 módulos | 🟡 |
| 5 | Código muerto (imports y variables sin uso) | 🟢 |
| 6 | ~130 líneas de lógica de parseo dentro de `app.py` (UI) | 🟠 (Fase 2) |
| 7 | Patrón `cache→gsheet→sqlite` duplicado en cada par save/load | 🟠 (Fase 2) |
| 8 | Flujo de PIN de supervisor es código inalcanzable en `auth._handle_login` | 🟢 (Fase 2) |

## 5. Problemas corregidos en esta fase

Los puntos **1–5** de la tabla anterior. Los puntos 6–8 quedan documentados para
Fase 2 porque tocarlos con seguridad requiere primero extender la red de tests a
la capa de UI/servicios.

## 6. Mejoras de rendimiento

Honestamente: **Fase 1 no busca rendimiento y no cambia el perfil de ejecución.**
No introduje ninguna optimización que altere resultados. Oportunidades detectadas
para Fase 2 (sin implementar aún): cachear `_gsheet_client()` con
`@st.cache_resource`, evitar relecturas completas de GSheet en cada `get_history`,
y reducir copias de DataFrame en el handler de carga.

## 7. Mejoras de mantenibilidad

- Una sola fuente de verdad para configuración → cambiar un peso o un umbral es
  editar una línea en `config/scoring.py`, no cazar números mágicos.
- Fallos de persistencia ahora quedan en logs → diagnosticables en Render.
- 80 tests documentan y protegen las reglas de negocio del motor de compensación.
- `ruff` integrado como linter; `requirements-dev.txt` separa tooling de prod.

## 8. Riesgos encontrados

- **Sin tests de UI/páginas**: `pages/` (la mayor parte de las 8.850 líneas) aún
  no tiene cobertura. Cualquier refactor de páginas en Fase 2 necesita primero
  tests de humo por página.
- **Seguridad — nota honesta**: mover emails/Slack IDs a `config/` mejora el orden,
  **no** la seguridad; son identificadores internos ya presentes en el repo. Los
  secretos reales (`GOOGLE_CREDS`, PIN) siguen — correctamente — en variables de
  entorno / `st.secrets`.
- **Persistencia frágil**: el límite de 49K de GSheet obliga a descartar payloads
  raw. Es una restricción de diseño, no un bug; conviene migrar el estado a un
  backend real (ver Fase 2).

## 9. Recomendaciones futuras (Fase 2, solo con tu OK)

1. Extraer la lógica de parseo de `app.py` a un servicio `services/ingest.py`
   testeable, dejando la página como pura orquestación de UI.
2. Unificar el patrón `cache→gsheet→sqlite` en una clase `SnapshotRepository`
   con una sola implementación del fallback en tres niveles (DRY).
3. Modelar los datos de farmer con una `dataclass FarmerMetrics` en vez de dicts.
4. Tests de humo por página (que cada `pages/*.py` importe y no lance).
5. Evaluar migrar de GSheets-como-BD a un Postgres gestionado (elimina el límite
   de 49K y las relecturas completas).
6. Limpiar el flujo de PIN de supervisor (actualmente inalcanzable).

## 10. Score del proyecto

Estimación cualitativa (no métrica automática), enfocada en salud de ingeniería:

| Dimensión | Antes | Después (Fase 1) |
|-----------|:-----:|:----------------:|
| Cobertura de tests | 0/10 | 6/10 |
| Configuración / magic numbers | 3/10 | 8/10 |
| Manejo de errores / observabilidad | 3/10 | 7/10 |
| Legibilidad (encoding, código muerto) | 5/10 | 8/10 |
| Separación de capas (UI vs lógica) | 3/10 | 4/10 *(Fase 2)* |
| **Global** | **≈3.5/10** | **≈6.5/10** |

El salto grande de Fase 2 (separación de capas, dataclasses, repositorios) solo
es seguro ahora que existe la red de tests que Fase 1 dejó instalada.
