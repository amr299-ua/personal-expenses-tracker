# Plan de Mejoras — Personal Expenses Tracker

> Fecha: 2026-05-02  
> Estado: Propuesta (Actualizada)  
> Proyecto: personal-expenses-tracker

---

## Resumen del proyecto

Aplicación de escritorio (Tkinter) y CLI para registrar ingresos y gastos personales con almacenamiento SQLite, gráficas matplotlib y exportación a CSV/Excel/PDF. Soporta 6 idiomas, tema claro/oscuro, filtros, ordenamiento y persistencia de estado de UI.

---

## 1. Base de datos y modelo de datos

### 1.1. Migraciones y ORM
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Implementar un sistema de migraciones robusto. Considerar la migración de `sqlite3` directo a **SQLAlchemy** con **Alembic** para facilitar el mantenimiento del esquema y la portabilidad. |

### 1.2. Tabla de categorías dedicada
| Prioridad | Descripción |
|-----------|-------------|
| Media | Extraer categorías a una tabla separada con FK desde `transactions`. Permitir marcar categorías como activas/inactivas y añadir iconos o colores personalizados. |

### 1.3. Campos adicionales y validación
| Prioridad | Descripción |
|-----------|-------------|
| Media | Añadir campo `currency` (moneda), `tags` (etiquetas múltiples), `recurring` (transacciones recurrentes). Usar **Pydantic** para validar los inputs antes de llegar a la BD. |

### 1.4. Optimización de consultas
| Prioridad | Descripción |
|-----------|-------------|
| Baja | Añadir índice compuesto `(transaction_date, transaction_type)` para consultas de rango con filtro por tipo. |

---

## 2. GUI (Interfaz gráfica)

### 2.1. Modernización estética
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Migrar de Tkinter estándar a **ttkbootstrap** o **CustomTkinter** para ofrecer una interfaz moderna, con soporte nativo para HiDPI y temas contemporáneos sin cambiar el motor base. |

### 2.2. Dashboard con gráficas embebidas
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Integrar gráficas matplotlib directamente en la GUI (tab "Estadísticas") usando `FigureCanvasTkAgg`. Implementar redimensionado dinámico de las gráficas. |

### 2.3. Paginación y Virtual Scrolling
| Prioridad | Descripción |
|-----------|-------------|
| Media | Implementar carga bajo demanda (lazy loading) en el Treeview para manejar miles de registros sin degradar el rendimiento. |

### 2.4. Atajos de teclado y Accesibilidad
| Prioridad | Descripción |
|-----------|-------------|
| Media | Implementar atajos globales (`Ctrl+N`, `Ctrl+F`, etc.) y mejorar el soporte para lectores de pantalla y navegación por teclado (foco visual claro). |

### 2.5. Validación en tiempo real
| Prioridad | Descripción |
|-----------|-------------|
| Media | Mostrar indicadores visuales (rojo/verde) y tooltips de error inline mientras el usuario escribe en el formulario. |

---

## 3. Gráficas y visualización

### 3.1. Gráficas interactivas
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Migrar de PNG estáticos a widgets interactivos que permitan hacer zoom, mostrar valores al pasar el ratón (tooltips) y filtrar series de datos. |

### 3.2. Nuevos tipos de análisis
| Prioridad | Descripción |
|-----------|-------------|
| Media | - Pronóstico de gastos basado en historial (regresión simple)  
| | - Gráfica de "Sankey" para flujo de ingresos -> gastos  
| | - Comparativa de gasto real vs. presupuesto planeado |

### 3.3. Personalización de colores
| Prioridad | Descripción |
|-----------|-------------|
| Baja | Permitir al usuario elegir paletas de colores accesibles (color-blind friendly). |

---

## 4. Exportación y reportes

### 4.1. Exportación inteligente
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Permitir exportar basándose exactamente en los filtros aplicados en pantalla. Añadir opción de "Exportación rápida" (último mes). |

### 4.2. Formatos modernos
| Prioridad | Descripción |
|-----------|-------------|
| Media | - **JSON/YAML** para portabilidad de datos  
| | - **HTML interactivo** con gráficas embebidas (usando Plotly o Chart.js offline)  
| | - Reporte mensual consolidado en PDF con resumen ejecutivo. |

### 4.3. Automatización
| Prioridad | Descripción |
|-----------|-------------|
| Baja | Generación programada de reportes y envío por email (opcional). |

---

## 5. Internacionalización (i18n)

### 5.1. Desacoplamiento de traducciones
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Mover las traducciones de `i18n.py` a archivos externos (`.json` o `.po/gettext`). Implementar un sistema de "hot-reload" de idioma sin reiniciar la app. |
| **Estado** | **Implementado** — Traducciones en archivos JSON externos (`locales/*.json`). `reload_translations()` recarga desde disco en `_on_language_change()` para hot-reload sin reiniciar. |

### 5.2. Formatos regionales (Locales)
| Prioridad | Descripción |
|-----------|-------------|
| Media | Adaptar automáticamente los formatos de fecha (`DD/MM/YYYY` vs `MM/DD/YYYY`) y separadores de miles/decimales según el idioma seleccionado. |
| **Estado** | **Implementado** — `format_date()` y `format_number()` en `i18n.py` usan la configuración regional del locale activo (meta `date_format`, `decimal_separator`, `thousands_separator`). Integrados en la GUI: Treeviews de transacciones, categorías, meses, tooltips de gráficas y labels de KPI.

### 5.3. Nuevos idiomas y contribución
| Prioridad | Descripción |
|-----------|-------------|
| Media | Añadir idiomas asiáticos y de derecha a izquierda (RTL). Crear una herramienta simple para que traductores externos añadan idiomas. |
| **Estado** | **Implementado** — Soporte RTL con `arabic-reshaper` y `python-bidi` para árabe (`ar`). Alineación derecha, reshaping de caracteres y justificación aplicados a widgets ttk.

---

## 6. Seguridad y privacidad

### 6.1. Protección de datos
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Implementar **SQLCipher** para encriptación AES-256 de la base de datos en reposo. Añadir pantalla de bloqueo por PIN/Contraseña al iniciar la app. |
| **Estado** | **Implementado** — `SQLCipherManager` gestiona claves de BD cifradas con Fernet (derivada del PIN). Bloqueo al inicio con `LockManager.is_lock_active()`. Migración de BD plaintext a cifrada con backup automático. Backups manuales y automáticos programados integrados.

### 6.2. Sincronización y Backups
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Implementar backups automáticos rotativos. Añadir soporte para sincronización opcional con servicios cloud (WebDAV, Dropbox, Google Drive) de forma cifrada. |
| **Estado** | **Implementado** — Backups automáticos programados (diarios/semanales/mensuales) vía `ReportScheduler._run_backup()` con checkbox en `AutomationDialog`. Rotación automática (`BackupManager.rotate_backups`). Módulo `cloud_sync.py` con proveedores WebDAV, Dropbox y Google Drive. `CloudSyncManager` cifra la BD con Fernet antes de subir. Diálogo GUI `cloud_sync_dialog.py` para configuración y sync manual.

### 6.3. Auditoría
| Prioridad | Descripción |
|-----------|-------------|
| Baja | Registro de cambios (`audit_log`) para rastrear ediciones accidentales. |
| **Estado** | **Implementado** — `AuditLog` en `security.py` (archivo JSONL) y tabla `audit_log` en la BD. Registra acciones CREATE, UPDATE, DELETE, LOGIN, BACKUP, RESTORE, LOCK_SET, LOCK_CHANGE. Accesible vía API y botón "View audit log".

---

## 7. Testing y Calidad

### 7.1. Automatización y Cobertura
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Configurar **GitHub Actions** completo: linting, tests y chequeo de tipos. Forzar cobertura >90% con `pytest-cov`. |
| **Estado** | **Implementado** — Workflow `.github/workflows/ci.yml` con jobs de lint/type-check y test para Python 3.10/3.11/3.12. Cobertura actual: **~92%** (excluyendo módulos de GUI pura). |

### 7.2. Testing Avanzado
| Prioridad | Descripción |
|-----------|-------------|
| Media | Introducir **Property-based testing** con `Hypothesis` para validar que el motor financiero maneje montos extremos y fechas límite correctamente. |
| **Estado** | **Implementado** — `tests/test_property_based.py` con tests de Hypothesis para montos extremos (0.01–1e9), fechas límite (1900–2100) y validación de balance/totals. |

### 7.3. Linting y Tipado
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Adoptar **Ruff** (más rápido que Flake8/Black) y **Mypy** en modo estricto. Configurar `pre-commit` hooks para prevenir regresiones. |
| **Estado** | **Implementado** — `pyproject.toml` con configuración de Ruff (lint + format) y Mypy strict. `.pre-commit-config.yaml` con hooks de Ruff, Mypy y utilidades básicas. `requirements-dev.txt` añadido. |

---

## 8. Arquitectura y Stack

### 8.1. Gestión de Dependencias
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Migrar a **uv** o **Poetry** para una gestión de dependencias moderna, rápida y reproducible. |

### 8.2. Refactorización Estructural
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Aplicar **Inyección de Dependencias** y separar `gui.py` en componentes desacoplados (Formularios, Tablas, Servicios de Negocio). |

### 8.3. Logging y Observabilidad
| Prioridad | Descripción |
|-----------|-------------|
| Media | Implementar un sistema de logging estructurado con rotación de archivos y niveles de severidad configurables. |

---

## 9. UX y Funcionalidades Nuevas

### 9.1. Presupuestos y Alertas
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Gestión de presupuestos mensuales por categoría con indicadores visuales de consumo (barras de progreso) y alertas de proximidad al límite. |

### 9.2. Inteligencia de Datos
| Prioridad | Descripción |
|-----------|-------------|
| Media | **Auto-categorización:** Sugerir categoría basada en la descripción usando algoritmos de texto sencillos o modelos locales ligeros. |

### 9.3. Gestión Multi-moneda
| Prioridad | Descripción |
|-----------|-------------|
| Media | Soporte para transacciones en monedas extranjeras con actualización automática (vía API) o manual de tasas de cambio. |

---

## 10. Distribución y Comunidad

### 10.1. Portabilidad
| Prioridad | Descripción |
|-----------|-------------|
| Media | Crear versión "Portable" que guarde toda la configuración y BD en la misma carpeta que el ejecutable. |

### 10.2. Documentación y Changelog
| Prioridad | Descripción |
|-----------|-------------|
| Alta | Mantener un `CHANGELOG.md` riguroso. Generar documentación técnica para desarrolladores usando MkDocs. |

### 10.3. Canales de Distribución
| Prioridad | Descripción |
|-----------|-------------|
| Media | Publicar instaladores firmados para Windows y paquetes `.deb`/`.rpm` para Linux. Considerar Flatpak/Snap. |

---

## Priorización sugerida (Roadmap Actualizado)

1.  **Fundamentos Modernos:** Migrar a `uv`, configurar `Ruff`/`Mypy` y habilitar CI (Fase 1).
2.  **Rediseño Visual:** Implementar `ttkbootstrap` y gráficas embebidas (Fase 2).
3.  **Core Financiero:** Presupuestos, recurrentes y migraciones con SQLAlchemy (Fase 2-3).
4.  **Seguridad y Cloud:** Encriptación SQLCipher y sincronización (Fase 4).
5.  **Inteligencia:** Auto-categorización y análisis predictivo (Fase 5).
