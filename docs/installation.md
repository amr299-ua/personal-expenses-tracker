# Installation

## Requirements

- **Python 3.10+**
- **System dependencies** (Linux):
  - `libsqlcipher-dev` — required for database encryption
  - `python3-tk` — required for the GUI

## Install from source

### Using uv (recommended)

```bash
git clone https://github.com/amr299-ua/personal-expenses-tracker.git
cd personal-expenses-tracker
uv sync
```

### Using pip + venv

```bash
git clone https://github.com/amr299-ua/personal-expenses-tracker.git
cd personal-expenses-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the application

```bash
# GUI mode (default)
python -m expenses_tracker

# CLI mode
python -m expenses_tracker --cli init-db
python -m expenses_tracker --cli add --type income --amount 2500 --category Salario --date 2026-05-11
python -m expenses_tracker --cli balance
```

## Build standalone executables

```bash
# Linux binary
./scripts/build_linux.sh

# Linux .deb package
./scripts/build_deb.sh

# Linux .rpm package
./scripts/build_rpm.sh

# macOS
./scripts/build_macos.sh
```

On Windows (PowerShell):

```powershell
./scripts/build_windows.ps1
```
