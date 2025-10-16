# Utils package for SIGE
# Import functions from the root utils.py file
import sys
import os

# Add parent directory to path to access utils.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now import from the utils.py file in parent directory  
try:
    # Import from the file directly
    import importlib.util
    spec = importlib.util.spec_from_file_location("utils_file", os.path.join(parent_dir, "utils.py"))
    utils_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils_module)
    
    # Export the functions
    calcular_valor_hora_corrigido = utils_module.calcular_valor_hora_corrigido
    calcular_valor_hora_periodo = utils_module.calcular_valor_hora_periodo
    calcular_custos_salariais_completos = utils_module.calcular_custos_salariais_completos
    calcular_dsr_modo_estrito = utils_module.calcular_dsr_modo_estrito
    calcular_horas_trabalhadas = utils_module.calcular_horas_trabalhadas
    
except Exception as e:
    print(f"Warning: Could not import functions from utils.py: {e}")
    # Provide dummy fallbacks
    def calcular_valor_hora_periodo(funcionario, data_inicio, data_fim):
        return 0.0
    def calcular_valor_hora_corrigido(funcionario):
        return 0.0