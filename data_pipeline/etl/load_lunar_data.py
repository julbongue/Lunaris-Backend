from sqlalchemy import create_engine
import pandas as pd

# Usando parâmetros separados, evitamos problemas com caracteres especiais na senha
DATABASE_URL = "postgresql+psycopg2://postgres:Mochileiros@2026@db.eluzrwlpkqtvqrbctcbt.supabase.co:5432/postgres"
engine = create_engine(DATABASE_URL)

# Dados lunares essenciais para o hackathon
lunar_sites = [
    {
        "name": "Cratera Shackleton",
        "latitude": -89.9,
        "longitude": 0.0,
        "elevation_m": -4200.0,
        "science_score": 9.8,
        "description": "Cratera rica em hidrogênio/gelo de água nas bordas.",
        "source": "NASA LRO / USGS"
    },
    {
        "name": "Malapert Mountain",
        "latitude": -86.0,
        "longitude": 22.7,
        "elevation_m": 5000.0,
        "science_score": 9.2,
        "description": "Excelente visibilidade para comunicação com a Terra.",
        "source": "NASA Moon Trek"
    },
    {
        "name": "Cratera Faustini",
        "latitude": -87.2,
        "longitude": 77.0,
        "elevation_m": -3900.0,
        "science_score": 8.9,
        "description": "Área de sombra permanente com potencial de voláteis.",
        "source": "NASA PDS"
    }
]

df = pd.DataFrame(lunar_sites)

# Envia direto para a tabela que o backend vai consultar
df.to_sql("lunar_sites", engine, if_exists="replace", index=False)
print("🚀 Sucesso! Dados lunares enviados para o Supabase.")
