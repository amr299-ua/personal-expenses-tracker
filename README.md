# personal-expenses-tracker

Aplicacion CLI en Python para control de ingresos y gastos personales.

Ahora la app abre una interfaz grafica interactiva por defecto.

## Fase 4 completada

Se creo la base del proyecto con:

- Estructura modular para CLI.
- Capa de datos con SQLite.
- Comandos iniciales para inicializar base, agregar movimientos, listar y ver balance.
- Resumenes por categoria y por mes.
- Generacion de graficas con matplotlib.
- Exportacion de reportes a Excel y PDF.
- PDF mejorado con portada visual, bloque KPI, resumen ejecutivo y tablas paginadas.
- Interfaz grafica interactiva (ventana) para registrar, revisar, graficar y exportar.
- Filtros interactivos y busqueda en vivo en la tabla de movimientos.
- Ordenamiento por columnas con clic en encabezados de la tabla.
- Filtros y orden guardados automaticamente entre sesiones.
- Atajos rapidos de fecha: hoy, semana, mes, año y todo.
- Selector visual de calendario para elegir fechas con clic.
- Rediseño visual moderno (tema, paleta, botones y tablas mejoradas).
- Modo claro/oscuro con cambio en tiempo real y persistencia.
- Tipos y filtros de movimientos totalmente en espanol.
- Categoria en desplegable con categorias tipicas (comida, luz, agua, gas, inversion, etc.).
- Selector de tipo de grafica desde la GUI al pulsar "Sacar graficas".
- Nuevas graficas: pastel (queso), puntos y barras 3D.

## Estructura actual

```text
personal-expenses-tracker/
	expenses_tracker/
		__init__.py
		__main__.py
		charts.py
		cli.py
		db.py
		exporters.py
	data/
	reports/
	tests/
	requirements.txt
	README.md
```

## Uso rapido

### Interfaz grafica (recomendado)

```bash
python -m expenses_tracker
```

### Modo consola (opcional)

```bash
python -m expenses_tracker --cli init-db
python -m expenses_tracker --cli add --type income --amount 2500 --category salario --date 2026-04-25 --description "Pago mensual"
python -m expenses_tracker --cli add --type expense --amount 120 --category transporte --date 2026-04-25 --description "Taxi"
python -m expenses_tracker --cli list --limit 10
python -m expenses_tracker --cli balance
python -m expenses_tracker --cli stats
python -m expenses_tracker --cli plot --type all --output-dir reports
python -m expenses_tracker --cli plot --type pie --output-dir reports
python -m expenses_tracker --cli plot --type scatter --output-dir reports
python -m expenses_tracker --cli plot --type bar3d --output-dir reports
python -m expenses_tracker --cli export --format all --output-dir reports
```

## Ejecutables sin consola

### Linux (generado en este proyecto)

```bash
./scripts/build_linux.sh
```

Importante: cada vez que cambies codigo, vuelve a ejecutar el script de build para que el ejecutable incluya todos los cambios nuevos.

Artefacto generado:

- `release/expenses-tracker-linux-x86_64.tar.gz`

Para ejecutar:

```bash
tar -xzf release/expenses-tracker-linux-x86_64.tar.gz -C release
./release/expenses-tracker
```

### Windows y macOS

No se compilan de forma fiable desde Linux. Para generar binarios nativos de Windows y macOS, usa el workflow:

- `.github/workflows/build-binaries.yml`

Ese workflow crea tres artefactos:

- `expenses-tracker-linux-x86_64`
- `expenses-tracker-windows-x86_64`
- `expenses-tracker-macos-arm64`

Tambien puedes compilar localmente en cada SO:

- Linux: `./scripts/build_linux.sh`
- macOS: `./scripts/build_macos.sh`
- Windows: `./scripts/build_windows.ps1`