"""Script para poblar la base de datos con datos de prueba realistas."""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from expenses_tracker.db import ExpenseDatabase

DB_PATH = Path(__file__).parent / "data" / "expenses.db"

# Categorías y datos por tipo
INCOME_ENTRIES = [
    ("Salario", "Nómina mensual"),
    ("Salario", "Pago quincenal"),
    ("Freelance", "Proyecto diseño web"),
    ("Freelance", "Consultoría IT"),
    ("Freelance", "Desarrollo app móvil"),
    ("Inversiones", "Dividendos acciones"),
    ("Inversiones", "Intereses cuenta ahorro"),
    ("Inversiones", "Fondos de inversión"),
    ("Alquiler", "Alquiler habitación"),
    ("Alquiler", "Renta local comercial"),
    ("Bonificación", "Bonus trimestral"),
    ("Bonificación", "Prima anual"),
    ("Otros ingresos", "Venta artículos segunda mano"),
    ("Otros ingresos", "Regalo cumpleaños"),
    ("Otros ingresos", "Devolución impuestos"),
]

EXPENSE_ENTRIES = [
    ("Alimentación", "Supermercado Mercadona"),
    ("Alimentación", "Compra semanal Lidl"),
    ("Alimentación", "Carnicería local"),
    ("Alimentación", "Frutería del barrio"),
    ("Restaurantes", "Comida en restaurante"),
    ("Restaurantes", "Cafetería desayuno"),
    ("Restaurantes", "Pizza delivery"),
    ("Restaurantes", "Bar tapas"),
    ("Transporte", "Tarjeta de transporte mensual"),
    ("Transporte", "Gasolina coche"),
    ("Transporte", "Parking centro"),
    ("Transporte", "Taxi/Cabify"),
    ("Transporte", "Revisión ITV"),
    ("Vivienda", "Alquiler mensual"),
    ("Vivienda", "Cuota hipoteca"),
    ("Vivienda", "Comunidad de vecinos"),
    ("Vivienda", "Seguro hogar"),
    ("Suministros", "Factura electricidad"),
    ("Suministros", "Factura gas"),
    ("Suministros", "Factura agua"),
    ("Suministros", "Factura internet"),
    ("Teléfono", "Cuota móvil mensual"),
    ("Teléfono", "Renovación plan datos"),
    ("Salud", "Consulta médico privado"),
    ("Salud", "Farmacia"),
    ("Salud", "Gafas/lentillas"),
    ("Salud", "Dentista revisión"),
    ("Salud", "Seguro médico"),
    ("Educación", "Matrícula curso online"),
    ("Educación", "Libros técnicos"),
    ("Educación", "Suscripción plataforma aprendizaje"),
    ("Ocio", "Cine"),
    ("Ocio", "Concierto"),
    ("Ocio", "Suscripción Netflix"),
    ("Ocio", "Suscripción Spotify"),
    ("Ocio", "PlayStation Network"),
    ("Ocio", "Videojuego Steam"),
    ("Ropa", "Zapatillas deporte"),
    ("Ropa", "Ropa temporada"),
    ("Ropa", "Accesorios"),
    ("Deporte", "Cuota gimnasio"),
    ("Deporte", "Material deportivo"),
    ("Viajes", "Vuelo ida y vuelta"),
    ("Viajes", "Hotel escapada"),
    ("Viajes", "Alquiler coche viaje"),
    ("Mascotas", "Comida perro/gato"),
    ("Mascotas", "Veterinario revisión"),
    ("Hogar", "Mueble/electrodoméstico"),
    ("Hogar", "Productos limpieza"),
    ("Hogar", "Reparación fontanero"),
    ("Suscripciones", "Amazon Prime"),
    ("Suscripciones", "Adobe Creative Cloud"),
    ("Suscripciones", "GitHub Pro"),
    ("Impuestos", "IRPF trimestral"),
    ("Impuestos", "IVA autónomo"),
    ("Banco", "Comisión mantenimiento cuenta"),
    ("Banco", "Comisión transferencia"),
    ("Regalos", "Regalo cumpleaños amigo"),
    ("Regalos", "Regalo navidad familia"),
    ("Emergencias", "Reparación coche avería"),
    ("Emergencias", "Electrodoméstico roto"),
]

# Rangos de importes por categoría
AMOUNT_RANGES = {
    "Salario": (1800, 3500),
    "Freelance": (300, 2000),
    "Inversiones": (50, 800),
    "Alquiler": (300, 900),
    "Bonificación": (200, 1500),
    "Otros ingresos": (20, 300),
    "Alimentación": (15, 150),
    "Restaurantes": (8, 80),
    "Transporte": (10, 150),
    "Vivienda": (400, 900),
    "Suministros": (30, 120),
    "Teléfono": (15, 40),
    "Salud": (20, 300),
    "Educación": (15, 200),
    "Ocio": (8, 60),
    "Ropa": (20, 200),
    "Deporte": (25, 80),
    "Viajes": (80, 800),
    "Mascotas": (20, 150),
    "Hogar": (15, 500),
    "Suscripciones": (5, 30),
    "Impuestos": (100, 600),
    "Banco": (2, 25),
    "Regalos": (20, 150),
    "Emergencias": (100, 1200),
}


def random_amount(category: str) -> float:
    """Return a random amount within the typical range for a category."""
    lo, hi = AMOUNT_RANGES.get(category, (10, 500))
    return round(random.uniform(lo, hi), 2)


def generate_dates(start: date, end: date, n: int) -> list[date]:
    """Generate n random sorted dates between start and end."""
    delta = (end - start).days
    return sorted(start + timedelta(days=random.randint(0, delta)) for _ in range(n))


def seed(n_transactions: int = 500) -> None:
    """Populate the database with sample transactions."""
    database = ExpenseDatabase(DB_PATH)
    database.initialize()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    end_date = date.today()
    start_date = end_date - timedelta(days=730)  # 2 años de datos

    dates = generate_dates(start_date, end_date, n_transactions)

    rows = []
    for d in dates:
        if random.random() < 0.25:  # 25% ingresos, 75% gastos
            cat, desc = random.choice(INCOME_ENTRIES)
            ttype = "income"
        else:
            cat, desc = random.choice(EXPENSE_ENTRIES)
            ttype = "expense"
        amount = random_amount(cat)
        rows.append((amount, ttype, cat, d.isoformat(), desc))

    cur.executemany(
        "INSERT INTO transactions (amount, transaction_type, category, transaction_date, description, currency, recurring, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'EUR', 0, datetime('now'))",
        rows,
    )
    conn.commit()

    count = cur.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    print(f"Insertados {len(rows)} registros. Total en BD: {count}")


if __name__ == "__main__":
    seed(500)
