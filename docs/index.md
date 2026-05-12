# Personal Expenses Tracker v1.0.0

Desktop and CLI application to track personal income and expenses.

## Overview

Personal Expenses Tracker is a full-featured personal finance application that runs on
Linux, macOS, and Windows. It offers both a modern GUI (built with Tkinter + ttkbootstrap)
and a full-featured CLI.

Key capabilities:

- **Transaction management**: Full CRUD with soft-delete, recurring transactions, multi-currency support
- **Budget planning**: Monthly budgets per category with progress indicators
- **8 chart types**: Bar, line, pie, scatter, 3D bar, forecast, Sankey, budget comparison
- **7 export formats**: CSV, Excel, PDF, JSON, YAML, HTML (Plotly), and consolidated monthly reports
- **Import**: CSV, Excel (.xlsx), and JSON with auto-detection
- **Security**: SQLCipher AES-256 encryption, PIN lock with rate limiting, Fernet encryption, audit logging
- **Cloud sync**: WebDAV, Dropbox, Google Drive with encrypted uploads
- **Automation**: Scheduled reports, backups, and email delivery
- **i18n**: 8 languages including RTL (Arabic) support

## Quick links

- [Installation Guide](installation.md)
- [User Guide](usage.md)
- [Security](security.md)
- [Development](architecture.md)
