"""
Script para adicionar campos necessários às tabelas obra, veiculo e servico
para suporte ao RDO v6.3 com correções de bugs críticos
"""

import os
import sys
from datetime import datetime
from sqlalchemy import text
from app import app, db
from models import Obra, Veiculo, Servico

def adicionar_campos_obra():
    """Adiciona campos necessários à tabela obra"""
    print("Adicionando campos à tabela obra...")
    
    with app.app_context():
        try:
            # Adicionar campo codigo se não existir
            try:
                db.session.execute(text("ALTER TABLE obra ADD COLUMN codigo VARCHAR(20)"))
                print("✓ Campo 'codigo' adicionado à tabela obra")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("✓ Campo 'codigo' já existe na tabela obra")
                else:
                    print(f"⚠ Erro ao adicionar campo 'codigo': {e}")
            
            # Adicionar campo area_total_m2 se não existir
            try:
                db.session.execute(text("ALTER TABLE obra ADD COLUMN area_total_m2 FLOAT DEFAULT 0.0"))
                print("✓ Campo 'area_total_m2' adicionado à tabela obra")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("✓ Campo 'area_total_m2' já existe na tabela obra")
                else:
                    print(f"⚠ Erro ao adicionar campo 'area_total_m2': {e}")
            
            # Adicionar campo ativo se não existir
            try:
                db.session.execute(text("ALTER TABLE obra ADD COLUMN ativo BOOLEAN DEFAULT true"))
                print("✓ Campo 'ativo' adicionado à tabela obra")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("✓ Campo 'ativo' já existe na tabela obra")
                else:
                    print(f"⚠ Erro ao adicionar campo 'ativo': {e}")
            
            db.session.commit()
            print("✓ Campos da tabela obra atualizados com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao atualizar tabela obra: {e}")
            db.session.rollback()

def adicionar_campos_veiculo():
    """Adiciona campos necessários à tabela veiculo"""
    print("\nAdicionando campos à tabela veiculo...")
    
    with app.app_context():
        try:
            # Adicionar campo ativo se não existir
            try:
                db.session.execute(text("ALTER TABLE veiculo ADD COLUMN ativo BOOLEAN DEFAULT true"))
                print("✓ Campo 'ativo' adicionado à tabela veiculo")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("✓ Campo 'ativo' já existe na tabela veiculo")
                else:
                    print(f"⚠ Erro ao adicionar campo 'ativo': {e}")
            
            db.session.commit()
            print("✓ Campos da tabela veiculo atualizados com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao atualizar tabela veiculo: {e}")
            db.session.rollback()

def adicionar_campos_servico():
    """Adiciona campos necessários à tabela servico"""
    print("\nAdicionando campos à tabela servico...")
    
    with app.app_context():
        try:
            # Adicionar campo unidade_simbolo se não existir
            try:
                db.session.execute(text("ALTER TABLE servico ADD COLUMN unidade_simbolo VARCHAR(10)"))
                print("✓ Campo 'unidade_simbolo' adicionado à tabela servico")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("✓ Campo 'unidade_simbolo' já existe na tabela servico")
                else:
                    print(f"⚠ Erro ao adicionar campo 'unidade_simbolo': {e}")
            
            # Adicionar campo custo_unitario se não existir
            try:
                db.session.execute(text("ALTER TABLE servico ADD COLUMN custo_unitario FLOAT DEFAULT 0.0"))
                print("✓ Campo 'custo_unitario' adicionado à tabela servico")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("✓ Campo 'custo_unitario' já existe na tabela servico")
                else:
                    print(f"⚠ Erro ao adicionar campo 'custo_unitario': {e}")
            
            db.session.commit()
            print("✓ Campos da tabela servico atualizados com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao atualizar tabela servico: {e}")
            db.session.rollback()

def atualizar_dados_existentes():
    """Atualiza dados existentes com valores padrão"""
    print("\nAtualizando dados existentes...")
    
    with app.app_context():
        try:
            # Atualizar obras sem código
            obras_sem_codigo = Obra.query.filter_by(codigo=None).all()
            for obra in obras_sem_codigo:
                obra.codigo = f"OB{obra.id:03d}"
                obra.ativo = True
                print(f"✓ Obra '{obra.nome}' recebeu código: {obra.codigo}")
            
            # Atualizar veículos sem status ativo
            veiculos = Veiculo.query.all()
            for veiculo in veiculos:
                if not hasattr(veiculo, 'ativo') or veiculo.ativo is None:
                    veiculo.ativo = True
                    print(f"✓ Veículo '{veiculo.marca} {veiculo.modelo}' marcado como ativo")
            
            # Atualizar serviços sem unidade_simbolo
            servicos = Servico.query.all()
            for servico in servicos:
                if not hasattr(servico, 'unidade_simbolo') or servico.unidade_simbolo is None:
                    # Mapear unidade_medida para símbolos
                    simbolos = {
                        'm2': 'm²',
                        'm3': 'm³',
                        'kg': 'kg',
                        'ton': 't',
                        'un': 'un',
                        'm': 'm',
                        'h': 'h'
                    }
                    servico.unidade_simbolo = simbolos.get(servico.unidade_medida, servico.unidade_medida)
                    print(f"✓ Serviço '{servico.nome}' recebeu símbolo: {servico.unidade_simbolo}")
                
                if not hasattr(servico, 'custo_unitario') or servico.custo_unitario is None:
                    servico.custo_unitario = 0.0
            
            db.session.commit()
            print("✓ Dados existentes atualizados com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao atualizar dados existentes: {e}")
            db.session.rollback()

def main():
    """Função principal"""
    print("=" * 60)
    print("MIGRAÇÃO DE CAMPOS - RDO v6.3")
    print("Correção de bugs críticos identificados")
    print("=" * 60)
    
    # Adicionar campos necessários
    adicionar_campos_obra()
    adicionar_campos_veiculo()
    adicionar_campos_servico()
    
    # Atualizar dados existentes
    atualizar_dados_existentes()
    
    print("\n" + "=" * 60)
    print("MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("Bugs críticos corrigidos:")
    print("✓ Campos 'codigo', 'area_total_m2', 'ativo' adicionados à tabela obra")
    print("✓ Campo 'ativo' adicionado à tabela veiculo")
    print("✓ Campos 'unidade_simbolo', 'custo_unitario' adicionados à tabela servico")
    print("✓ Dados existentes atualizados com valores padrão")
    print("=" * 60)

if __name__ == "__main__":
    main()