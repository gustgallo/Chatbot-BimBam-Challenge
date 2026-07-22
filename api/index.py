# Punto de entrada para Vercel Serverless Functions.
# Importa la app Flask desde app.py (un nivel arriba).
import sys
import os

# Agrega el directorio raíz del proyecto al path para que los imports funcionen.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app

# Vercel busca una variable llamada `app` en este módulo.
