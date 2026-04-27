# Personal Expenses Tracker

Aplicacion de escritorio y linea de comandos para registrar ingresos y gastos personales, con almacenamiento local en SQLite, graficas PNG y exportacion a Excel/PDF.

## Tabla de contenido

- [Resumen](#resumen)
- [Caracteristicas](#caracteristicas)
- [Stack tecnico](#stack-tecnico)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Requisitos](#requisitos)
- [Instalacion](#instalacion)
- [Uso rapido](#uso-rapido)
- [Referencia CLI](#referencia-cli)
- [Archivos generados](#archivos-generados)
- [Build de ejecutables](#build-de-ejecutables)
- [Estado del proyecto](#estado-del-proyecto)
- [Licencia](#licencia)
- [Contribucion](#contribucion)

## Resumen

Este proyecto permite:

- Registrar movimientos (ingresos y gastos).
- Consultar balance global y estadisticas por categoria/mes.
- Visualizar datos con varias graficas.
- Exportar reportes listos para compartir.

La aplicacion abre la GUI por defecto. El modo CLI se activa con el flag especial `--cli`.

## Caracteristicas

- GUI en Tkinter con tres secciones: registro, movimientos y estadisticas.
- Filtros en vivo por texto, tipo, categoria y rango de fechas.
- Ordenamiento por columnas en tabla de movimientos.
- Persistencia de preferencias de interfaz en `data/ui_state.json` (tema, filtros y orden).
- Atajos de fecha: hoy, semana, mes, ano y todo.
- Selector de fecha con calendario visual.
- Graficas con matplotlib:
	- Barras por categoria.
	- Evolucion mensual (linea).
	- Distribucion de ingresos/gastos (pastel).
	- Puntos mensuales con linea de balance.
	- Barras 3D por mes.
- Exportacion a Excel (`.xlsx`) y PDF (`.pdf`) con:
	- Portada.
	- KPI principales.
	- Resumen ejecutivo.
	- Tablas paginadas por categoria, mes y movimientos.

## Stack tecnico

- Python 3.10+
- SQLite (base local)
- Tkinter (GUI)
- matplotlib + numpy (graficas)
- openpyxl (Excel)
- reportlab (PDF)
- PyInstaller (empaquetado)

## Estructura del proyecto

```text
personal-expenses-tracker/
	expenses_tracker/
		__main__.py        # Entrada principal (GUI por defecto / CLI con --cli)
		gui.py             # Interfaz grafica
		cli.py             # Comandos de consola
		db.py              # Capa de datos SQLite
		charts.py          # Generacion de graficas
		exporters.py       # Exportacion Excel/PDF
	scripts/
		build_linux.sh
		build_macos.sh
		build_windows.ps1
	data/                # Base SQLite y estado de UI
	reports/             # Graficas y reportes generados
	run_gui.py           # Entry point alternativo para GUI
	requirements.txt
	requirements-build.txt
```

## Requisitos

- Python 3.10 o superior.
- pip actualizado.

## Instalacion

```bash
git clone <URL_DEL_REPOSITORIO>
cd personal-expenses-tracker

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

## Uso rapido

### 1) GUI (modo recomendado)

```bash
python -m expenses_tracker
```

Alternativa equivalente:

```bash
python run_gui.py
```

### 2) CLI

```bash
python -m expenses_tracker --cli init-db

python -m expenses_tracker --cli add \
	--type income \
	--amount 2500 \
	--category Salario \
	--date 2026-04-25 \
	--description "Pago mensual"

python -m expenses_tracker --cli add \
	--type expense \
	--amount 120 \
	--category Transporte \
	--date 2026-04-25 \
	--description "Taxi"

python -m expenses_tracker --cli list --limit 20
python -m expenses_tracker --cli balance
python -m expenses_tracker --cli stats
python -m expenses_tracker --cli plot --type all --output-dir reports
python -m expenses_tracker --cli export --format all --output-dir reports
```

## Referencia CLI

Comando base:

```bash
python -m expenses_tracker --cli [--db-path RUTA_DB] <comando> [opciones]
```

Comandos disponibles:

- `init-db`: crea tablas e indices en SQLite.
- `add`: registra un movimiento.
	- `--type`: `income` o `expense`.
	- `--amount`: monto positivo.
	- `--category`: categoria.
	- `--date`: formato `YYYY-MM-DD`.
	- `--description`: texto opcional.
- `list`: lista movimientos recientes (`--limit`, default `20`).
- `balance`: muestra balance total.
- `stats`: resumen por categoria y por mes.
- `plot`: genera graficas PNG (`--type` y `--output-dir`).
	- `--type`: `category`, `month`, `bar`, `line`, `pie`, `scatter`, `bar3d`, `all`.
- `export`: exporta reportes (`--format` y `--output-dir`).
	- `--format`: `excel`, `pdf`, `all`.

## Archivos generados

Por defecto, el proyecto usa estas rutas:

- Base de datos: `data/expenses.db`
- Estado GUI: `data/ui_state.json`
- Graficas: `reports/chart_*.png`
- Reportes: `reports/report_*.xlsx`, `reports/report_*.pdf`

## Build de ejecutables

Los scripts de build usan PyInstaller en modo `--windowed --onefile` sobre `run_gui.py`.

### Linux

```bash
./scripts/build_linux.sh
```

Salida esperada:

- `release/expenses-tracker-linux-<arquitectura>.tar.gz`

Ejemplo de ejecucion:

```bash
tar -xzf release/expenses-tracker-linux-x86_64.tar.gz -C release
./release/expenses-tracker
```

### macOS

```bash
./scripts/build_macos.sh
```

Salida esperada:

- `release/expenses-tracker-macos-<arquitectura>.tar.gz`

### Windows (PowerShell)

```powershell
./scripts/build_windows.ps1
```

Salida esperada:

- `release/expenses-tracker-windows-x86_64.zip`

## Estado del proyecto

- El repositorio incluye estructura para pruebas (`tests/`), pero actualmente no hay tests implementados.
- No hay pipeline CI/CD incluido en el repo en este momento.

## Licencia

Este proyecto se distribuye bajo la licencia Apache-2.0. Consulta [LICENSE](LICENSE).

## Contribucion

Sugerencias para colaborar:

1. Crear un entorno virtual limpio.
2. Mantener compatibilidad de comandos CLI existentes.
3. Agregar pruebas para nuevas funciones en capa de datos, CLI y exportadores.
4. Documentar cambios de comportamiento en este README.