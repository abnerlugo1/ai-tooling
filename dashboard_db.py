"""
Módulo y herramienta CLI para convertir y gestionar el archivo Excel 'dashboard .xlsx'
como una base de datos relacional SQLite a través de Python.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

# Rutas predeterminadas relativas al directorio del archivo/proyecto
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_EXCEL_PATH = Path(os.getenv("EXCEL_PATH", str(BASE_DIR / "Documents" / "dashboard .xlsx")))
DEFAULT_DB_PATH = Path(os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "Documents" / "dashboard.db")))


class DashboardDB:
    """Gestiona la base de datos SQLite sincronizada con el archivo Excel."""

    TABLE_NAME = "dashboard"

    def __init__(
        self,
        excel_path: Union[str, Path] = DEFAULT_EXCEL_PATH,
        db_path: Union[str, Path] = DEFAULT_DB_PATH,
    ) -> None:
        self.excel_path = Path(excel_path)
        self.db_path = Path(db_path)

    def init_db(self, force_reload: bool = False) -> int:
        """
        Lee el archivo Excel, limpia y tipifica los datos, y los inserta en SQLite.
        Retorna la cantidad de registros insertados.
        """
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Archivo Excel no encontrado en: {self.excel_path}")

        # Si la base de datos ya existe y no se fuerza recarga, solo verificamos
        if self.db_path.exists() and not force_reload:
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{self.TABLE_NAME}'")
                if cur.fetchone()[0] > 0:
                    cur.execute(f"SELECT COUNT(*) FROM {self.TABLE_NAME}")
                    return cur.fetchone()[0]
            finally:
                conn.close()

        # Leer Excel
        df = pd.read_excel(self.excel_path, sheet_name=0)

        # Normalización de tipos de datos
        df["id"] = df["id"].astype(int)
        df["cliente"] = df["cliente"].astype(str).str.strip()
        df["edad"] = df["edad"].astype(int)
        df["genero"] = df["genero"].astype(str).str.strip().str.upper()
        df["num_cuenta"] = df["num_cuenta"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        df["categoria"] = df["categoria"].astype(str).str.strip()
        df["servicio"] = df["servicio"].astype(str).str.strip()
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%Y-%m-%d")

        # Conectar a SQLite y crear tabla estructurada con tipos e índices
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()

            # Crear tabla
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id INTEGER PRIMARY KEY,
                    cliente TEXT NOT NULL,
                    edad INTEGER NOT NULL,
                    genero TEXT NOT NULL,
                    num_cuenta TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    servicio TEXT NOT NULL,
                    fecha TEXT NOT NULL
                )
            """)

            # Limpiar tabla previa
            cur.execute(f"DELETE FROM {self.TABLE_NAME}")

            # Insertar registros
            records = [
                (
                    int(row["id"]),
                    str(row["cliente"]),
                    int(row["edad"]),
                    str(row["genero"]),
                    str(row["num_cuenta"]),
                    str(row["categoria"]),
                    str(row["servicio"]),
                    str(row["Fecha"]),
                )
                for _, row in df.iterrows()
            ]

            cur.executemany(
                f"""
                INSERT INTO {self.TABLE_NAME} (id, cliente, edad, genero, num_cuenta, categoria, servicio, fecha)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )

            # Crear índices para acelerar búsquedas
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_cliente ON {self.TABLE_NAME} (cliente)")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_categoria ON {self.TABLE_NAME} (categoria)")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_servicio ON {self.TABLE_NAME} (servicio)")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_fecha ON {self.TABLE_NAME} (fecha)")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_genero ON {self.TABLE_NAME} (genero)")

            conn.commit()
        finally:
            conn.close()

        return len(df)

    def get_connection(self, read_only: bool = False) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos con acceso tipo diccionario (sqlite3.Row)."""
        if not self.db_path.exists():
            self.init_db()
        if read_only:
            db_uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
            conn = sqlite3.connect(db_uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql: str, params: Tuple[Any, ...] = (), read_only: bool = True) -> List[Dict[str, Any]]:
        """Ejecuta una consulta SQL en modo protegido (sólo lectura por defecto)."""
        conn = self.get_connection(read_only=read_only)
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def query_df(self, sql: str, params: Tuple[Any, ...] = (), read_only: bool = True) -> pd.DataFrame:
        """Ejecuta una consulta SQL en modo de sólo lectura y retorna un DataFrame de pandas."""
        conn = self.get_connection(read_only=read_only)
        try:
            return pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Calcula métricas clave analíticas de la base de datos."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()

            # Total registros y clientes únicos
            cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT cliente), MIN(edad), MAX(edad), AVG(edad) FROM {self.TABLE_NAME}")
            total, unique_clients, min_age, max_age, avg_age = cur.fetchone()

            # Rango de fechas
            cur.execute(f"SELECT MIN(fecha), MAX(fecha) FROM {self.TABLE_NAME}")
            min_date, max_date = cur.fetchone()

            # Distribución por género
            cur.execute(f"SELECT genero, COUNT(*) as count FROM {self.TABLE_NAME} GROUP BY genero ORDER BY count DESC")
            gender_dist = {r["genero"]: r["count"] for r in cur.fetchall()}

            # Top categorías
            cur.execute(f"SELECT categoria, COUNT(*) as count FROM {self.TABLE_NAME} GROUP BY categoria ORDER BY count DESC LIMIT 5")
            top_categories = {r["categoria"]: r["count"] for r in cur.fetchall()}

            # Top servicios
            cur.execute(f"SELECT servicio, COUNT(*) as count FROM {self.TABLE_NAME} GROUP BY servicio ORDER BY count DESC LIMIT 5")
            top_services = {r["servicio"]: r["count"] for r in cur.fetchall()}

            return {
                "total_registros": total,
                "clientes_unicos": unique_clients,
                "edad_minima": min_age,
                "edad_maxima": max_age,
                "edad_promedio": round(avg_age, 1) if avg_age else 0,
                "fecha_inicio": min_date,
                "fecha_fin": max_date,
                "distribucion_genero": gender_dist,
                "top_categorias": top_categories,
                "top_servicios": top_services,
                "db_path": str(self.db_path),
            }
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Gestor de base de datos SQLite para 'dashboard .xlsx'",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Comando sync
    parser_sync = subparsers.add_parser("sync", help="Sincronizar y cargar el archivo Excel en SQLite")
    parser_sync.add_argument("--force", action="store_true", help="Forzar reimportación completa")

    # Comando query
    parser_query = subparsers.add_parser("query", help="Ejecutar una consulta SQL")
    parser_query.add_argument("sql", help="Consulta SQL a ejecutar")
    parser_query.add_argument("--limit", type=int, default=20, help="Límite de filas mostradas")

    # Comando stats
    subparsers.add_parser("stats", help="Mostrar resumen analítico de los datos")

    args = parser.parse_args()

    db = DashboardDB()

    if args.command == "sync" or args.command is None:
        force = getattr(args, "force", False)
        print(f"[*] Sincronizando '{db.excel_path.name}' -> '{db.db_path.name}'...")
        total = db.init_db(force_reload=force)
        print(f"[OK] Base de datos SQLite lista con {total:,} registros en: {db.db_path}")

    elif args.command == "query":
        print(f"[*] Ejecutando SQL: {args.sql}\n")
        df = db.query_df(args.sql)
        if len(df) > args.limit:
            print(df.head(args.limit).to_string(index=False))
            print(f"\n... Mostrando {args.limit} de {len(df)} resultados.")
        else:
            print(df.to_string(index=False))

    elif args.command == "stats":
        stats = db.get_summary_metrics()
        print("\n" + "=" * 60)
        print("          RESUMEN ANALÍTICO DE LA BASE DE DATOS")
        print("=" * 60)
        print(f"Total de Registros  : {stats['total_registros']:,}")
        print(f"Clientes Únicos     : {stats['clientes_unicos']:,}")
        print(f"Rango de Edades     : {stats['edad_minima']} - {stats['edad_maxima']} años (Promedio: {stats['edad_promedio']})")
        print(f"Período Registrado  : {stats['fecha_inicio']} a {stats['fecha_fin']}")
        print(f"\nDistribución por Género:")
        for gen, count in stats['distribucion_genero'].items():
            pct = (count / stats['total_registros']) * 100
            print(f"  - {gen}: {count:,} ({pct:.1f}%)")
        print(f"\nTop 5 Categorías:")
        for cat, count in stats['top_categorias'].items():
            pct = (count / stats['total_registros']) * 100
            print(f"  - {cat}: {count:,} ({pct:.1f}%)")
        print(f"\nTop 5 Servicios:")
        for srv, count in stats['top_servicios'].items():
            pct = (count / stats['total_registros']) * 100
            print(f"  - {srv}: {count:,} ({pct:.1f}%)")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
