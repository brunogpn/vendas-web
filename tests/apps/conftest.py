import os
import sys

# Os apps usam imports "planos" (from apps..., import database), como no container (app/ copiado
# para /app); aqui app/ entra no path para testá-los fora do Docker.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app'))
