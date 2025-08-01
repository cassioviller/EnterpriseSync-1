#!/usr/bin/env python3
"""
Migração dos Tipos de Registro para Padronização v8.2
Atualiza todos os registros existentes para os tipos padronizados conforme documento oficial

Autor: Sistema SIGE v8.2
Data: 1º de agosto de 2025
"""

from app import app, db
from models import RegistroPonto
from datetime import datetime

def migrar_tipos_padronizados():
    """
    Migra os tipos de registro existentes para os tipos padronizados:
    
    TIPOS PADRONIZADOS CONFORME DOCUMENTO:
    1. trabalho_normal - Jornada regular (segunda a sexta)
    2. sabado_trabalhado - Sábado trabalhado (+50%)
    3. domingo_trabalhado - Domingo trabalhado (+100%)
    4. feriado_trabalhado - Feriado trabalhado (+100%)
    5. falta - Falta sem justificativa (desconta)
    6. falta_justificada - Falta justificada (remunerada)
    7. ferias - Férias (+33%)
    8. folga_sabado - Folga sábado
    9. folga_domingo - Folga domingo
    10. folga_feriado - Folga feriado
    """
    
    with app.app_context():
        print("🔄 MIGRAÇÃO DOS TIPOS DE REGISTRO PARA v8.2")
        print("=" * 60)
        
        # Mapeamento dos tipos antigos para os novos
        mapeamento_tipos = {
            # Tipos antigos -> tipos padronizados
            'trabalhado': 'trabalho_normal',
            'trabalho_normal': 'trabalho_normal',
            'trabalho': 'trabalho_normal',
            
            'sabado_horas_extras': 'sabado_trabalhado',
            'sabado_extra': 'sabado_trabalhado',
            'sabado_trabalhado': 'sabado_trabalhado',
            
            'domingo_horas_extras': 'domingo_trabalhado',
            'domingo_extra': 'domingo_trabalhado',
            'domingo_trabalhado': 'domingo_trabalhado',
            
            'feriado_horas_extras': 'feriado_trabalhado',
            'feriado_extra': 'feriado_trabalhado',
            'feriado_trabalhado': 'feriado_trabalhado',
            
            'falta': 'falta',
            'falta_injustificada': 'falta',
            
            'falta_justificada': 'falta_justificada',
            'falta_medica': 'falta_justificada',
            'atestado': 'falta_justificada',
            
            'ferias': 'ferias',
            'periodo_ferias': 'ferias',
            
            'folga': 'folga_sabado',  # Assumir sábado por padrão
            'sabado_folga': 'folga_sabado',
            'domingo_folga': 'folga_domingo',
            'feriado_folga': 'folga_feriado'
        }
        
        # Buscar todos os registros
        registros = RegistroPonto.query.all()
        total_registros = len(registros)
        
        print(f"📊 Total de registros a processar: {total_registros}")
        
        # Contadores para estatísticas
        migrados = 0
        tipos_encontrados = {}
        tipos_migrados = {}
        
        for registro in registros:
            tipo_original = registro.tipo_registro or 'trabalho_normal'
            
            # Contar tipos encontrados
            tipos_encontrados[tipo_original] = tipos_encontrados.get(tipo_original, 0) + 1
            
            # Determinar novo tipo
            novo_tipo = mapeamento_tipos.get(tipo_original, tipo_original)
            
            # Para folgas, usar dia da semana para determinar tipo específico
            if novo_tipo == 'folga_sabado' and registro.data:
                dia_semana = registro.data.weekday()  # 0=Segunda, 6=Domingo
                if dia_semana == 5:  # Sábado
                    novo_tipo = 'folga_sabado'
                elif dia_semana == 6:  # Domingo
                    novo_tipo = 'folga_domingo'
            
            # Atualizar se necessário
            if registro.tipo_registro != novo_tipo:
                registro.tipo_registro = novo_tipo
                migrados += 1
                
                # Contar tipos migrados
                tipos_migrados[novo_tipo] = tipos_migrados.get(novo_tipo, 0) + 1
        
        # Salvar alterações
        try:
            db.session.commit()
            print(f"✅ Migração concluída! {migrados} registros atualizados")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na migração: {e}")
            return False
        
        # Exibir estatísticas
        print(f"\n📈 ESTATÍSTICAS DA MIGRAÇÃO:")
        print("-" * 40)
        
        print("TIPOS ENCONTRADOS:")
        for tipo, qtd in sorted(tipos_encontrados.items()):
            print(f"  {tipo}: {qtd} registros")
        
        print(f"\nTIPOS MIGRADOS:")
        for tipo, qtd in sorted(tipos_migrados.items()):
            print(f"  {tipo}: {qtd} registros")
        
        # Verificar distribuição final
        print(f"\n📊 DISTRIBUIÇÃO FINAL DOS TIPOS:")
        print("-" * 40)
        
        tipos_finais = db.session.query(
            RegistroPonto.tipo_registro,
            db.func.count(RegistroPonto.id)
        ).group_by(RegistroPonto.tipo_registro).all()
        
        for tipo, qtd in tipos_finais:
            print(f"  {tipo or 'NULL'}: {qtd} registros")
        
        return True

def validar_tipos_padronizados():
    """Valida se todos os tipos estão padronizados"""
    
    with app.app_context():
        print("\n🔍 VALIDAÇÃO DOS TIPOS PADRONIZADOS")
        print("=" * 50)
        
        # Tipos válidos conforme documento
        tipos_validos = {
            'trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado',
            'feriado_trabalhado', 'falta', 'falta_justificada', 'ferias',
            'folga_sabado', 'folga_domingo', 'folga_feriado'
        }
        
        # Verificar tipos únicos no banco
        tipos_banco = db.session.query(RegistroPonto.tipo_registro).distinct().all()
        tipos_banco = {t[0] for t in tipos_banco if t[0]}
        
        # Identificar tipos inválidos
        tipos_invalidos = tipos_banco - tipos_validos
        tipos_faltantes = tipos_validos - tipos_banco
        
        if tipos_invalidos:
            print(f"⚠️  TIPOS INVÁLIDOS ENCONTRADOS:")
            for tipo in sorted(tipos_invalidos):
                qtd = db.session.query(RegistroPonto).filter(
                    RegistroPonto.tipo_registro == tipo
                ).count()
                print(f"   {tipo}: {qtd} registros")
        
        if tipos_faltantes:
            print(f"ℹ️  TIPOS PADRÃO NÃO UTILIZADOS:")
            for tipo in sorted(tipos_faltantes):
                print(f"   {tipo}")
        
        if not tipos_invalidos:
            print("✅ TODOS OS TIPOS ESTÃO PADRONIZADOS!")
        
        return len(tipos_invalidos) == 0

if __name__ == "__main__":
    print("🚀 INICIANDO MIGRAÇÃO PARA TIPOS PADRONIZADOS v8.2")
    print("=" * 70)
    
    # Executar migração
    sucesso = migrar_tipos_padronizados()
    
    if sucesso:
        # Validar resultado
        validar_tipos_padronizados()
        
        print(f"\n🎉 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("Sistema SIGE v8.2 com tipos padronizados ativo.")
    else:
        print(f"\n❌ MIGRAÇÃO FALHOU!")
        print("Verifique os logs de erro acima.")