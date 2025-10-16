"""
Script de migração para recalcular horas_trabalhadas de registros antigos.
Executa UMA VEZ para corrigir dados históricos onde hora_entrada/hora_saida
foram preenchidos mas horas_trabalhadas ficou zerado.
"""

from app import app, db
from models import RegistroPonto
from datetime import datetime, timedelta

def calcular_horas_trabalhadas(entrada, saida, almoco_saida=None, almoco_retorno=None):
    """
    Calcula horas trabalhadas considerando intervalo de almoço.
    
    Args:
        entrada: hora de entrada (time)
        saida: hora de saída (time)
        almoco_saida: hora de saída para almoço (time, opcional)
        almoco_retorno: hora de retorno do almoço (time, opcional)
    
    Returns:
        float: horas trabalhadas arredondadas para 2 casas decimais
    """
    if not entrada or not saida:
        return 0.0
    
    # Converte time para datetime para fazer cálculos
    hoje = datetime.today().date()
    dt_entrada = datetime.combine(hoje, entrada)
    dt_saida = datetime.combine(hoje, saida)
    
    # Se saída é antes da entrada, assumir que passou da meia-noite
    if dt_saida < dt_entrada:
        dt_saida += timedelta(days=1)
    
    # Calcula total de horas
    total = (dt_saida - dt_entrada).total_seconds() / 3600
    
    # Desconta intervalo de almoço se houver
    if almoco_saida and almoco_retorno:
        dt_almoco_saida = datetime.combine(hoje, almoco_saida)
        dt_almoco_retorno = datetime.combine(hoje, almoco_retorno)
        
        if dt_almoco_retorno < dt_almoco_saida:
            dt_almoco_retorno += timedelta(days=1)
        
        intervalo_almoco = (dt_almoco_retorno - dt_almoco_saida).total_seconds() / 3600
        total -= intervalo_almoco
    else:
        # Desconta 1h de almoço padrão se trabalhou mais de 6h
        if total > 6:
            total -= 1
    
    return round(total, 2)

def main():
    """Função principal de migração"""
    with app.app_context():
        # Busca todos os registros com horas_trabalhadas = 0 mas que têm entrada/saída
        registros = RegistroPonto.query.filter(
            RegistroPonto.horas_trabalhadas == 0,
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        print(f"🔍 Encontrados {len(registros)} registros para recalcular")
        
        if len(registros) == 0:
            print("✅ Nenhum registro precisa ser atualizado!")
            return
        
        contador = 0
        erros = 0
        
        for registro in registros:
            try:
                horas = calcular_horas_trabalhadas(
                    registro.hora_entrada,
                    registro.hora_saida,
                    registro.hora_almoco_saida,
                    registro.hora_almoco_retorno
                )
                
                registro.horas_trabalhadas = horas
                contador += 1
                
                if contador % 100 == 0:
                    print(f"⏳ Processados {contador}/{len(registros)} registros...")
                    db.session.commit()  # Commit parcial a cada 100
            
            except Exception as e:
                erros += 1
                print(f"❌ Erro no registro ID {registro.id}: {str(e)}")
        
        # Commit final
        db.session.commit()
        
        print(f"\n{'='*60}")
        print(f"✅ Migração concluída com sucesso!")
        print(f"📊 Estatísticas:")
        print(f"   - Total processado: {contador} registros")
        print(f"   - Erros: {erros} registros")
        print(f"   - Taxa de sucesso: {(contador/(contador+erros)*100) if (contador+erros) > 0 else 100:.1f}%")
        print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
