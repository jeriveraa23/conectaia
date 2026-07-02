import os
import pandas as pd
from sqlalchemy import create_engine, text


class Database:

    def __init__(self):
        user = os.environ["POSTGRES_USER"]
        password = os.environ["POSTGRES_PASSWORD"]
        host = os.environ["POSTGRES_HOST"]
        port = os.environ["POSTGRES_PORT"]
        db = os.environ["POSTGRES_DB"]

        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
        self.engine = create_engine(url)

    def _fix_numeric_columns(self, df):
        """Limpia columnas de texto que contienen números con formatos no estándar."""
        columnas_codigo = [c for c in df.columns if c.startswith("codigo_")]
        for col in df.columns:
            if col in columnas_codigo:
                continue
            if df[col].dtype == object:
                muestra = df[col].dropna().head(100)
                if len(muestra) == 0:
                    continue
                if not hasattr(muestra, 'str'):
                    continue
                es_numero = muestra.str.match(r"^-?[\d,\.]+$", na=False).any()
                if es_numero:
                    df[col] = (
                        df[col]
                        .str.replace(r"(?<=\d),(?=\d{3})", "", regex=True)
                        .str.replace(",", ".")
                    )
                    try:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    except Exception:
                        pass
        return df

    def load(self, df, schema, table, if_exists="append"):
        """Carga un DataFrame a schema.table, agregando loaded_at."""
        df = df.copy()
        df = self._fix_numeric_columns(df)
        df["loaded_at"] = pd.Timestamp.now()

        with self.engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {schema}.{table}"))

        df.to_sql(table, self.engine, schema=schema, if_exists=if_exists, index=False)

    def read(self, query):
        """Ejecuta un SQL y retorna un DataFrame."""
        return pd.read_sql(query, self.engine)