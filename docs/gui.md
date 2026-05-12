# GUI Reference

## Layout

The main window has four tabs:

| Tab | Shortcut | Purpose |
|-----|----------|---------|
| Register | `Ctrl+1` | Add new transactions |
| Transactions | `Ctrl+2` | Browse, filter, sort, edit, delete |
| Statistics | `Ctrl+3` | Charts and summary statistics |
| Budgets | `Ctrl+4` | Monthly budget planning |

## Toolbar

Located at the top of the window:

- **Refresh** (`F5`): Reload all data
- **Import**: Open file dialog to import CSV/Excel/JSON
- **Export format dropdown**: Select target format for export
- **Export**: Export with current filters
- **Quick Export** (`Ctrl+E`): Export all formats for latest month

## Header

- Application title and subtitle
- Three KPI metric cards: Balance, Total Income, Total Expense
- Language switcher (combobox)
- Theme toggle button (light ↔ dark)
- Color palette selector (default, colorblind-friendly, dark)

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | Focus new transaction form |
| `Ctrl+F` | Focus search field |
| `Ctrl+S` | Save current form |
| `F5` | Refresh data |
| `Ctrl+G` | Open chart viewer |
| `Ctrl+E` | Quick export |
| `Ctrl+1`–`4` | Switch tabs |
| `Alt+R` | Refresh |
| `Alt+T` | Toggle theme |
| `Alt+I` | Import file |
| `Escape` | Focus search field |

## Menu bar

### File
- **Import**: Import transactions from file
- **Export**: Export transactions (respects current filters)
- **Close**: Exit application

### View
- **Theme**: Toggle light/dark
- **Language**: Select language
- **Palette**: Select color palette

### Tools
- **Charts** (`Ctrl+G`): Open chart viewer dialog
- **Automation**: Configure scheduled reports and backups
- **Backup**: Manual database backup
- **Cloud Sync**: Configure cloud providers (WebDAV, Dropbox, Google Drive)
- **Set PIN Lock**: Enable/change PIN protection
- **Encrypt Database**: Enable SQLCipher encryption

## Theme and appearance

The application uses **ttkbootstrap** for modern styling.
Two themes available:

- **Light** (`flatly`): Clean, modern light theme
- **Dark** (`darkly`): Dark theme for low-light environments

Three color palettes for charts:

- **Default**: Standard seaborn-inspired palette
- **Colorblind**: Accessible palette for color vision deficiency
- **Dark**: Optimized for dark backgrounds
