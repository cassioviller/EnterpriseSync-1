"""
SISTEMA DE VALIDAÇÕES ROBUSTO PARA RDO
Implementa validações críticas identificadas na análise
"""

from flask import current_app
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple, Optional
import re

def validar_rdo_completo(form_data: Dict, rdo_id: Optional[int] = None) -> Dict:
    """
    Validação completa de RDO com todas as regras críticas
    Retorna dicionário com status e lista de erros
    """
    errors = []
    warnings = []
    
    # Importar modelos apenas quando necessário
    from models import RDO, RDOMaoObra, RDOEquipamento, RDOAtividade, Funcionario, Obra
    from app import db
    
    try:
        # 1. VALIDAÇÕES BÁSICAS
        obra_id = form_data.get('obra_id')
        data_relatorio_str = form_data.get('data_relatorio')
        
        if not obra_id:
            errors.append("Obra é obrigatória")
            
        if not data_relatorio_str:
            errors.append("Data do relatório é obrigatória")
        
        # Se validações básicas falharam, retornar imediatamente
        if errors:
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Converter data
        try:
            if isinstance(data_relatorio_str, str):
                data_relatorio = datetime.strptime(data_relatorio_str, '%Y-%m-%d').date()
            else:
                data_relatorio = data_relatorio_str
        except (ValueError, TypeError):
            errors.append("Data do relatório inválida")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # 2. VALIDAÇÃO: RDO ÚNICO POR DIA/OBRA
        resultado_unico = validar_rdo_unico_por_dia(obra_id, data_relatorio, rdo_id)
        if not resultado_unico['valid']:
            errors.extend(resultado_unico['errors'])
        
        # 3. VALIDAÇÃO: DATA RELATÓRIO
        resultado_data = validar_data_relatorio(data_relatorio)
        if not resultado_data['valid']:
            errors.extend(resultado_data['errors'])
        if resultado_data['warnings']:
            warnings.extend(resultado_data['warnings'])
        
        # 4. VALIDAÇÃO: ATIVIDADES
        atividades = form_data.get('atividades', [])
        if isinstance(atividades, str):
            try:
                import json
                atividades = json.loads(atividades)
            except:
                atividades = []
        
        resultado_atividades = validar_atividades(atividades)
        if not resultado_atividades['valid']:
            errors.extend(resultado_atividades['errors'])
        if resultado_atividades['warnings']:
            warnings.extend(resultado_atividades['warnings'])
        
        # 5. VALIDAÇÃO: MÃO DE OBRA
        mao_obra = form_data.get('mao_obra', [])
        if isinstance(mao_obra, str):
            try:
                import json
                mao_obra = json.loads(mao_obra)
            except:
                mao_obra = []
        
        resultado_mao_obra = validar_mao_obra(mao_obra, data_relatorio, rdo_id)
        if not resultado_mao_obra['valid']:
            errors.extend(resultado_mao_obra['errors'])
        if resultado_mao_obra['warnings']:
            warnings.extend(resultado_mao_obra['warnings'])
        
        # 6. VALIDAÇÃO: EQUIPAMENTOS
        equipamentos = form_data.get('equipamentos', [])
        if isinstance(equipamentos, str):
            try:
                import json
                equipamentos = json.loads(equipamentos)
            except:
                equipamentos = []
        
        resultado_equipamentos = validar_equipamentos(equipamentos, obra_id, data_relatorio, rdo_id)
        if not resultado_equipamentos['valid']:
            errors.extend(resultado_equipamentos['errors'])
        if resultado_equipamentos['warnings']:
            warnings.extend(resultado_equipamentos['warnings'])
        
        # 7. VALIDAÇÃO: CAMPOS CLIMÁTICOS
        resultado_clima = validar_campos_climaticos(form_data)
        if not resultado_clima['valid']:
            errors.extend(resultado_clima['errors'])
        if resultado_clima['warnings']:
            warnings.extend(resultado_clima['warnings'])
        
        # 8. VALIDAÇÃO: OCORRÊNCIAS
        ocorrencias = form_data.get('ocorrencias', [])
        if isinstance(ocorrencias, str):
            try:
                import json
                ocorrencias = json.loads(ocorrencias)
            except:
                ocorrencias = []
        
        resultado_ocorrencias = validar_ocorrencias(ocorrencias)
        if not resultado_ocorrencias['valid']:
            errors.extend(resultado_ocorrencias['errors'])
        if resultado_ocorrencias['warnings']:
            warnings.extend(resultado_ocorrencias['warnings'])
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_errors': len(errors),
            'total_warnings': len(warnings)
        }
        
    except Exception as e:
        current_app.logger.error(f"Erro validação RDO: {str(e)}")
        return {
            'valid': False,
            'errors': [f"Erro interno na validação: {str(e)}"],
            'warnings': warnings
        }

def validar_rdo_unico_por_dia(obra_id: int, data_relatorio: date, rdo_id: Optional[int] = None) -> Dict:
    """Valida se RDO é único para obra/data"""
    from models import RDO
    from app import db
    
    try:
        query = RDO.query.filter_by(obra_id=obra_id, data_relatorio=data_relatorio)
        if rdo_id:
            query = query.filter(RDO.id != rdo_id)
        
        rdo_existente = query.first()
        
        if rdo_existente:
            return {
                'valid': False,
                'errors': [f"Já existe RDO {rdo_existente.numero_rdo} para esta obra na data {data_relatorio.strftime('%d/%m/%Y')}"],
                'warnings': []
            }
        
        return {'valid': True, 'errors': [], 'warnings': []}
        
    except Exception as e:
        return {
            'valid': False,
            'errors': [f"Erro ao verificar RDO único: {str(e)}"],
            'warnings': []
        }

def validar_data_relatorio(data_relatorio: date) -> Dict:
    """Valida data do relatório"""
    errors = []
    warnings = []
    
    hoje = date.today()
    
    # Data não pode ser futura
    if data_relatorio > hoje:
        errors.append("Data do relatório não pode ser futura")
    
    # Alertar se data muito antiga (mais de 30 dias)
    limite_passado = hoje - timedelta(days=30)
    if data_relatorio < limite_passado:
        warnings.append(f"Data do relatório é muito antiga (anterior a {limite_passado.strftime('%d/%m/%Y')})")
    
    # Alertar se não é dia útil (fins de semana)
    if data_relatorio.weekday() >= 5:  # 5=sábado, 6=domingo
        warnings.append("Data do relatório é fim de semana")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

def validar_atividades(atividades: List[Dict]) -> Dict:
    """Valida lista de atividades"""
    errors = []
    warnings = []
    
    if not atividades:
        warnings.append("Nenhuma atividade informada")
        return {'valid': True, 'errors': errors, 'warnings': warnings}
    
    for i, atividade in enumerate(atividades, 1):
        # Validar descrição
        descricao = atividade.get('descricao', '').strip()
        if not descricao:
            errors.append(f"Atividade {i}: Descrição é obrigatória")
            continue
        
        if len(descricao) < 10:
            warnings.append(f"Atividade {i}: Descrição muito curta")
        
        # Validar percentual
        try:
            percentual = float(atividade.get('percentual', 0))
            if not (0 <= percentual <= 100):
                errors.append(f"Atividade {i}: Percentual deve estar entre 0% e 100% (atual: {percentual}%)")
            
            if percentual == 0:
                warnings.append(f"Atividade {i}: Nenhum progresso informado")
        except (ValueError, TypeError):
            errors.append(f"Atividade {i}: Percentual deve ser um número válido")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

def validar_mao_obra(mao_obra: List[Dict], data_relatorio: date, rdo_id: Optional[int] = None) -> Dict:
    """Valida mão de obra"""
    from models import RDOMaoObra, RDO, Funcionario
    from app import db
    
    errors = []
    warnings = []
    
    if not mao_obra:
        warnings.append("Nenhuma mão de obra informada")
        return {'valid': True, 'errors': errors, 'warnings': warnings}
    
    funcionarios_registrados = set()
    
    for i, mo in enumerate(mao_obra, 1):
        funcionario_id = mo.get('funcionario_id')
        if not funcionario_id:
            errors.append(f"Funcionário {i}: ID é obrigatório")
            continue
        
        try:
            funcionario_id = int(funcionario_id)
        except (ValueError, TypeError):
            errors.append(f"Funcionário {i}: ID deve ser numérico")
            continue
        
        # Verificar duplicata no mesmo RDO
        if funcionario_id in funcionarios_registrados:
            errors.append(f"Funcionário {i}: Já registrado neste RDO")
            continue
        
        funcionarios_registrados.add(funcionario_id)
        
        # Validar funcionário existe
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            errors.append(f"Funcionário {i}: Não encontrado")
            continue
        
        # Validar funcionário ativo
        if not funcionario.ativo:
            warnings.append(f"Funcionário {i} ({funcionario.nome}): Está inativo")
        
        # Validar função
        funcao = mo.get('funcao', '').strip()
        if not funcao:
            warnings.append(f"Funcionário {i} ({funcionario.nome}): Função não informada")
        
        # Validar horas trabalhadas
        try:
            horas = float(mo.get('horas', 8))
            
            if horas <= 0:
                errors.append(f"Funcionário {i} ({funcionario.nome}): Horas trabalhadas deve ser maior que zero")
                continue
            
            if horas > 12:
                errors.append(f"Funcionário {i} ({funcionario.nome}): Não pode trabalhar mais que 12h por dia (CLT). Informado: {horas}h")
                continue
            
            # Verificar se funcionário já tem horas registradas na data
            try:
                total_existente = db.session.query(
                    db.func.sum(RDOMaoObra.horas_trabalhadas)
                ).join(RDO).filter(
                    RDOMaoObra.funcionario_id == funcionario_id,
                    RDO.data_relatorio == data_relatorio,
                    RDO.id != rdo_id if rdo_id else True
                ).scalar() or 0
                
                if total_existente + horas > 12:
                    errors.append(f"Funcionário {funcionario.nome}: Excederia {total_existente + horas}h no total (máximo 12h/dia). Já possui {total_existente}h registradas em outros RDOs.")
                
            except Exception as e:
                warnings.append(f"Não foi possível verificar horas anteriores do funcionário {funcionario.nome}")
            
            # Alertas para horas extras
            if horas > 8:
                warnings.append(f"Funcionário {funcionario.nome}: {horas - 8}h extras registradas")
        
        except (ValueError, TypeError):
            errors.append(f"Funcionário {i} ({funcionario.nome}): Horas trabalhadas deve ser um número válido")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

def validar_equipamentos(equipamentos: List[Dict], obra_id: int, data_relatorio: date, rdo_id: Optional[int] = None) -> Dict:
    """Valida equipamentos"""
    from models import RDOEquipamento, RDO
    from app import db
    
    errors = []
    warnings = []
    
    if not equipamentos:
        return {'valid': True, 'errors': errors, 'warnings': warnings}
    
    equipamentos_registrados = {}
    
    for i, eq in enumerate(equipamentos, 1):
        nome = eq.get('nome', '').strip()
        if not nome:
            errors.append(f"Equipamento {i}: Nome é obrigatório")
            continue
        
        # Verificar duplicata no mesmo RDO
        if nome.lower() in equipamentos_registrados:
            warnings.append(f"Equipamento {i}: '{nome}' já registrado neste RDO")
        
        equipamentos_registrados[nome.lower()] = True
        
        # Validar quantidade
        try:
            quantidade = int(eq.get('quantidade', 1))
            if quantidade <= 0:
                errors.append(f"Equipamento {i} ({nome}): Quantidade deve ser maior que zero")
        except (ValueError, TypeError):
            errors.append(f"Equipamento {i} ({nome}): Quantidade deve ser um número inteiro")
            continue
        
        # Validar horas de uso
        try:
            horas_uso = float(eq.get('horas_uso', 8))
            
            if horas_uso <= 0:
                errors.append(f"Equipamento {i} ({nome}): Horas de uso deve ser maior que zero")
                continue
            
            if horas_uso > 24:
                errors.append(f"Equipamento {i} ({nome}): Não pode usar mais que 24h por dia. Informado: {horas_uso}h")
                continue
            
            # Verificar disponibilidade do equipamento na data
            try:
                total_existente = db.session.query(
                    db.func.sum(RDOEquipamento.horas_uso)
                ).join(RDO).filter(
                    RDOEquipamento.nome_equipamento.ilike(f'%{nome}%'),
                    RDO.obra_id == obra_id,
                    RDO.data_relatorio == data_relatorio,
                    RDO.id != rdo_id if rdo_id else True
                ).scalar() or 0
                
                total_com_novas = total_existente + horas_uso
                if total_com_novas > 24:
                    warnings.append(f"Equipamento '{nome}': Pode exceder 24h de uso no total ({total_com_novas}h). Já possui {total_existente}h registradas.")
            
            except Exception:
                pass  # Ignorar erro de verificação
        
        except (ValueError, TypeError):
            errors.append(f"Equipamento {i} ({nome}): Horas de uso deve ser um número válido")
        
        # Validar estado de conservação
        estado = eq.get('estado', '').strip()
        if not estado:
            warnings.append(f"Equipamento {i} ({nome}): Estado de conservação não informado")
        elif estado.lower() in ['ruim', 'péssimo', 'quebrado']:
            warnings.append(f"Equipamento {nome}: Estado de conservação preocupante ({estado})")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

def validar_campos_climaticos(form_data: Dict) -> Dict:
    """Valida campos climáticos"""
    errors = []
    warnings = []
    
    # Validar umidade se informada
    umidade = form_data.get('umidade_relativa')
    if umidade is not None:
        try:
            umidade_int = int(umidade)
            if not (0 <= umidade_int <= 100):
                errors.append("Umidade relativa deve estar entre 0% e 100%")
        except (ValueError, TypeError):
            errors.append("Umidade relativa deve ser um número inteiro")
    
    # Validar temperatura se informada
    temperatura = form_data.get('temperatura_media', '').strip()
    if temperatura:
        # Verificar formato básico (número + °C)
        if not re.match(r'^\d+(\.\d+)?\s*°?[CF]?$', temperatura):
            warnings.append("Formato de temperatura recomendado: '25°C'")
    
    # Verificar consistência clima vs condições de trabalho
    clima_geral = form_data.get('clima_geral', '').lower()
    condicoes_trabalho = form_data.get('condicoes_trabalho', '').lower()
    
    if clima_geral == 'chuvoso' and condicoes_trabalho == 'ideais':
        warnings.append("Condições 'ideais' para trabalho podem ser inconsistentes com clima 'chuvoso'")
    
    if clima_geral in ['tempestade', 'chuva forte'] and condicoes_trabalho not in ['limitadas', 'inadequadas']:
        warnings.append("Clima severo pode exigir condições de trabalho mais restritivas")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

def validar_ocorrencias(ocorrencias: List[Dict]) -> Dict:
    """Valida ocorrências"""
    errors = []
    warnings = []
    
    if not ocorrencias:
        return {'valid': True, 'errors': errors, 'warnings': warnings}
    
    for i, oc in enumerate(ocorrencias, 1):
        # Validar descrição
        descricao = oc.get('descricao', '').strip()
        if not descricao:
            errors.append(f"Ocorrência {i}: Descrição é obrigatória")
            continue
        
        if len(descricao) < 10:
            warnings.append(f"Ocorrência {i}: Descrição muito curta")
        
        # Validar tipo
        tipo = oc.get('tipo', 'Observação')
        tipos_validos = ['Problema', 'Observação', 'Melhoria', 'Segurança']
        if tipo not in tipos_validos:
            warnings.append(f"Ocorrência {i}: Tipo '{tipo}' não reconhecido. Tipos válidos: {', '.join(tipos_validos)}")
        
        # Validar severidade
        severidade = oc.get('severidade', 'Baixa')
        severidades_validas = ['Baixa', 'Média', 'Alta', 'Crítica']
        if severidade not in severidades_validas:
            warnings.append(f"Ocorrência {i}: Severidade '{severidade}' não reconhecida")
        
        # Alertas especiais
        if severidade == 'Crítica':
            warnings.append(f"Ocorrência {i}: Marcada como CRÍTICA - atenção especial necessária")
        
        if tipo == 'Segurança':
            warnings.append(f"Ocorrência {i}: Relacionada à SEGURANÇA - verificar protocolos")
        
        # Validar prazo de resolução se informado
        prazo_str = oc.get('prazo_resolucao', '').strip()
        if prazo_str:
            try:
                prazo = datetime.strptime(prazo_str, '%Y-%m-%d').date()
                if prazo < date.today():
                    warnings.append(f"Ocorrência {i}: Prazo de resolução já passou ({prazo.strftime('%d/%m/%Y')})")
            except ValueError:
                warnings.append(f"Ocorrência {i}: Formato de data do prazo inválido (use YYYY-MM-DD)")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

# Função auxiliar para validações específicas
def validar_campo_obrigatorio(valor: str, nome_campo: str) -> bool:
    """Valida se campo obrigatório foi preenchido"""
    return bool(valor and valor.strip())

def validar_numero_positivo(valor, nome_campo: str) -> Tuple[bool, str]:
    """Valida se valor é número positivo"""
    try:
        num = float(valor)
        if num <= 0:
            return False, f"{nome_campo} deve ser maior que zero"
        return True, ""
    except (ValueError, TypeError):
        return False, f"{nome_campo} deve ser um número válido"

def validar_percentual(valor, nome_campo: str) -> Tuple[bool, str]:
    """Valida se valor é percentual válido (0-100)"""
    try:
        num = float(valor)
        if not (0 <= num <= 100):
            return False, f"{nome_campo} deve estar entre 0% e 100%"
        return True, ""
    except (ValueError, TypeError):
        return False, f"{nome_campo} deve ser um número válido"

def validar_data_formato(data_str: str, nome_campo: str) -> Tuple[bool, str, Optional[date]]:
    """Valida formato de data"""
    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
        return True, "", data_obj
    except ValueError:
        return False, f"{nome_campo} deve estar no formato YYYY-MM-DD", None

if __name__ == "__main__":
    # Teste básico das validações
    print("=== TESTE DO SISTEMA DE VALIDAÇÕES RDO ===")
    
    # Dados de teste
    form_data_teste = {
        'obra_id': 1,
        'data_relatorio': '2025-08-17',
        'atividades': [
            {'descricao': 'Teste atividade', 'percentual': 50}
        ],
        'mao_obra': [
            {'funcionario_id': 1, 'funcao': 'Soldador', 'horas': 8}
        ],
        'umidade_relativa': 65,
        'temperatura_media': '25°C'
    }
    
    # resultado = validar_rdo_completo(form_data_teste)
    # print(f"Validação: {'✅ VÁLIDO' if resultado['valid'] else '❌ INVÁLIDO'}")
    # if resultado['errors']:
    #     print(f"Erros: {resultado['errors']}")
    # if resultado['warnings']:
    #     print(f"Avisos: {resultado['warnings']}")
    
    print("✅ Sistema de validações carregado com sucesso!")