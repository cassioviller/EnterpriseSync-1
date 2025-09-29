#!/usr/bin/env python3
# ================================
# FLEET MIGRATION - SCRIPT DEFINITIVO PARA PRODUÇÃO
# ================================
# Migração completa e segura do sistema de veículos legacy para FLEET
# Inclui backup automático, validação e rollback

import os
import sys
import logging
import traceback
from datetime import datetime, date
from decimal import Decimal
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fleet_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FleetMigration:
    """
    Classe para migração segura e robusta do sistema de veículos.
    """
    
    def __init__(self):
        self.backup_data = {}
        self.migration_stats = {
            'inicio': datetime.now(),
            'veiculos_migrados': 0,
            'usos_migrados': 0,
            'custos_migrados': 0,
            'erros': []
        }
    
    def setup_flask_app(self):
        """Setup do ambiente Flask"""
        try:
            # Adicionar diretório atual ao path
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            
            # Importar Flask e models
            from app import app, db
            
            # Importar models legacy
            from models import Veiculo, UsoVeiculo, CustoVeiculo
            
            # Importar novos models FLEET
            from fleet_models import FleetVehicle, FleetVehicleUsage, FleetVehicleCost
            
            self.app = app
            self.db = db
            self.Veiculo = Veiculo
            self.UsoVeiculo = UsoVeiculo
            self.CustoVeiculo = CustoVeiculo
            self.FleetVehicle = FleetVehicle
            self.FleetVehicleUsage = FleetVehicleUsage
            self.FleetVehicleCost = FleetVehicleCost
            
            logger.info("✅ Flask app configurado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no setup Flask: {e}")
            return False
    
    def verificar_ambiente(self):
        """Verificar se é ambiente de produção ou desenvolvimento"""
        database_url = os.environ.get('DATABASE_URL', '')
        
        if 'neon.tech' in database_url:
            ambiente = 'DESENVOLVIMENTO'
        elif any(prod_indicator in database_url.lower() for prod_indicator in ['prod', 'production', 'hostinger', 'easypanel']):
            ambiente = 'PRODUÇÃO'
        else:
            ambiente = 'DESENVOLVIMENTO'
        
        logger.info(f"🏭 AMBIENTE DETECTADO: {ambiente}")
        logger.info(f"🔗 DATABASE: {database_url[:50]}...")
        
        return ambiente
    
    def verificar_prerequisitos(self):
        """Verificar se todas as condições estão atendidas"""
        try:
            with self.app.app_context():
                # Verificar se tabelas legacy existem
                legacy_tables = ['veiculo', 'uso_veiculo', 'custo_veiculo']
                existing_tables = []
                
                for table in legacy_tables:
                    try:
                        result = self.db.session.execute(f"SELECT COUNT(*) FROM {table}")
                        count = result.scalar()
                        existing_tables.append((table, count))
                        logger.info(f"✅ Tabela {table}: {count} registros")
                    except Exception as e:
                        logger.warning(f"⚠️ Tabela {table} não encontrada: {e}")
                
                # Verificar se tabelas FLEET já existem
                fleet_tables = ['fleet_vehicle', 'fleet_vehicle_usage', 'fleet_vehicle_cost']
                fleet_exists = []
                
                for table in fleet_tables:
                    try:
                        result = self.db.session.execute(f"SELECT COUNT(*) FROM {table}")
                        count = result.scalar()
                        fleet_exists.append((table, count))
                        logger.warning(f"⚠️ Tabela FLEET {table} já existe: {count} registros")
                    except Exception as e:
                        logger.info(f"✅ Tabela FLEET {table} não existe (ok)")
                        fleet_exists.append((table, 0))
                
                return {
                    'legacy_tables': existing_tables,
                    'fleet_tables': fleet_exists,
                    'ready': len(existing_tables) > 0
                }
                
        except Exception as e:
            logger.error(f"❌ Erro na verificação de pré-requisitos: {e}")
            return {'ready': False, 'error': str(e)}
    
    def fazer_backup_completo(self):
        """Fazer backup completo dos dados legacy"""
        try:
            logger.info("💾 Iniciando backup completo das tabelas legacy...")
            
            with self.app.app_context():
                # Backup de veículos
                veiculos = self.Veiculo.query.all()
                self.backup_data['veiculos'] = []
                for veiculo in veiculos:
                    self.backup_data['veiculos'].append(veiculo.to_dict())
                
                logger.info(f"💾 Backup veículos: {len(veiculos)} registros")
                
                # Backup de usos
                usos = self.UsoVeiculo.query.all()
                self.backup_data['usos'] = []
                for uso in usos:
                    self.backup_data['usos'].append(uso.to_dict())
                
                logger.info(f"💾 Backup usos: {len(usos)} registros")
                
                # Backup de custos
                custos = self.CustoVeiculo.query.all()
                self.backup_data['custos'] = []
                for custo in custos:
                    self.backup_data['custos'].append(custo.to_dict())
                
                logger.info(f"💾 Backup custos: {len(custos)} registros")
                
                # Salvar backup em arquivo
                backup_filename = f"fleet_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(backup_filename, 'w', encoding='utf-8') as f:
                    json.dump(self.backup_data, f, ensure_ascii=False, indent=2, default=str)
                
                logger.info(f"💾 Backup salvo em: {backup_filename}")
                return backup_filename
                
        except Exception as e:
            logger.error(f"❌ Erro no backup: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def criar_tabelas_fleet(self):
        """Criar tabelas FLEET no banco de dados"""
        try:
            logger.info("🏗️ Criando tabelas FLEET...")
            
            with self.app.app_context():
                # Criar tabelas usando SQLAlchemy
                self.db.create_all()
                
                # Verificar se foram criadas
                fleet_tables = ['fleet_vehicle', 'fleet_vehicle_usage', 'fleet_vehicle_cost']
                
                for table in fleet_tables:
                    try:
                        result = self.db.session.execute(f"SELECT COUNT(*) FROM {table}")
                        logger.info(f"✅ Tabela {table} criada com sucesso")
                    except Exception as e:
                        logger.error(f"❌ Erro ao verificar tabela {table}: {e}")
                        return False
                
                logger.info("🏗️ Todas as tabelas FLEET criadas com sucesso")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabelas FLEET: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def migrar_veiculos(self):
        """Migrar dados de veículos legacy para FLEET"""
        try:
            logger.info("🚗 Iniciando migração de veículos...")
            
            with self.app.app_context():
                veiculos_legacy = self.Veiculo.query.all()
                
                for veiculo in veiculos_legacy:
                    try:
                        # Verificar se já foi migrado
                        existing = self.FleetVehicle.query.filter_by(
                            reg_plate=veiculo.placa,
                            admin_owner_id=veiculo.admin_id
                        ).first()
                        
                        if existing:
                            logger.info(f"⚠️ Veículo {veiculo.placa} já migrado, pulando...")
                            continue
                        
                        # Criar novo registro FLEET
                        novo_veiculo = self.FleetVehicle(
                            reg_plate=veiculo.placa,
                            make_name=veiculo.marca,
                            model_name=veiculo.modelo or 'Não informado',
                            vehicle_year=veiculo.ano,
                            vehicle_kind=veiculo.tipo or 'Veículo',
                            current_km=veiculo.km_atual or 0,
                            vehicle_color=veiculo.cor,
                            chassis_number=veiculo.chassi,
                            renavam_code=veiculo.renavam,
                            fuel_type=veiculo.combustivel or 'Gasolina',
                            status_code='ativo' if veiculo.ativo else 'inativo',
                            last_maintenance_date=veiculo.data_ultima_manutencao,
                            next_maintenance_date=veiculo.data_proxima_manutencao,
                            next_maintenance_km=veiculo.km_proxima_manutencao,
                            admin_owner_id=veiculo.admin_id,
                            created_at=veiculo.created_at,
                            updated_at=veiculo.updated_at
                        )
                        
                        self.db.session.add(novo_veiculo)
                        self.migration_stats['veiculos_migrados'] += 1
                        
                        if self.migration_stats['veiculos_migrados'] % 10 == 0:
                            self.db.session.commit()
                            logger.info(f"🚗 Migrados {self.migration_stats['veiculos_migrados']} veículos...")
                        
                    except Exception as e:
                        logger.error(f"❌ Erro ao migrar veículo {veiculo.id}: {e}")
                        self.migration_stats['erros'].append(f"Veículo {veiculo.id}: {e}")
                        continue
                
                self.db.session.commit()
                logger.info(f"✅ Migração de veículos concluída: {self.migration_stats['veiculos_migrados']} registros")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro na migração de veículos: {e}")
            logger.error(traceback.format_exc())
            self.db.session.rollback()
            return False
    
    def migrar_usos(self):
        """Migrar dados de usos de veículos"""
        try:
            logger.info("🚌 Iniciando migração de usos de veículos...")
            
            with self.app.app_context():
                usos_legacy = self.UsoVeiculo.query.all()
                
                for uso in usos_legacy:
                    try:
                        # Encontrar veículo FLEET correspondente
                        veiculo_legacy = self.Veiculo.query.get(uso.veiculo_id)
                        if not veiculo_legacy:
                            logger.warning(f"⚠️ Veículo legacy {uso.veiculo_id} não encontrado para uso {uso.id}")
                            continue
                        
                        veiculo_fleet = self.FleetVehicle.query.filter_by(
                            reg_plate=veiculo_legacy.placa,
                            admin_owner_id=veiculo_legacy.admin_id
                        ).first()
                        
                        if not veiculo_fleet:
                            logger.warning(f"⚠️ Veículo FLEET não encontrado para placa {veiculo_legacy.placa}")
                            continue
                        
                        # Verificar se já foi migrado
                        existing = self.FleetVehicleUsage.query.filter_by(
                            vehicle_id=veiculo_fleet.vehicle_id,
                            usage_date=uso.data_uso,
                            driver_id=uso.motorista_id
                        ).first()
                        
                        if existing:
                            logger.info(f"⚠️ Uso {uso.id} já migrado, pulando...")
                            continue
                        
                        # Criar novo registro FLEET
                        novo_uso = self.FleetVehicleUsage(
                            vehicle_id=veiculo_fleet.vehicle_id,
                            driver_id=uso.motorista_id,
                            worksite_id=uso.obra_id,
                            usage_date=uso.data_uso,
                            departure_time=uso.hora_saida,
                            return_time=uso.hora_retorno,
                            start_km=uso.km_inicial,
                            end_km=uso.km_final,
                            distance_km=uso.km_percorrido,
                            front_passengers=uso.passageiros_frente,
                            rear_passengers=uso.passageiros_tras,
                            vehicle_responsible=uso.responsavel_veiculo,
                            usage_notes=uso.observacoes,
                            admin_owner_id=uso.admin_id,
                            created_at=uso.created_at,
                            updated_at=uso.updated_at
                        )
                        
                        self.db.session.add(novo_uso)
                        self.migration_stats['usos_migrados'] += 1
                        
                        if self.migration_stats['usos_migrados'] % 20 == 0:
                            self.db.session.commit()
                            logger.info(f"🚌 Migrados {self.migration_stats['usos_migrados']} usos...")
                        
                    except Exception as e:
                        logger.error(f"❌ Erro ao migrar uso {uso.id}: {e}")
                        self.migration_stats['erros'].append(f"Uso {uso.id}: {e}")
                        continue
                
                self.db.session.commit()
                logger.info(f"✅ Migração de usos concluída: {self.migration_stats['usos_migrados']} registros")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro na migração de usos: {e}")
            logger.error(traceback.format_exc())
            self.db.session.rollback()
            return False
    
    def migrar_custos(self):
        """Migrar dados de custos de veículos"""
        try:
            logger.info("💰 Iniciando migração de custos de veículos...")
            
            with self.app.app_context():
                custos_legacy = self.CustoVeiculo.query.all()
                
                for custo in custos_legacy:
                    try:
                        # Encontrar veículo FLEET correspondente
                        veiculo_legacy = self.Veiculo.query.get(custo.veiculo_id)
                        if not veiculo_legacy:
                            logger.warning(f"⚠️ Veículo legacy {custo.veiculo_id} não encontrado para custo {custo.id}")
                            continue
                        
                        veiculo_fleet = self.FleetVehicle.query.filter_by(
                            reg_plate=veiculo_legacy.placa,
                            admin_owner_id=veiculo_legacy.admin_id
                        ).first()
                        
                        if not veiculo_fleet:
                            logger.warning(f"⚠️ Veículo FLEET não encontrado para placa {veiculo_legacy.placa}")
                            continue
                        
                        # Verificar se já foi migrado
                        existing = self.FleetVehicleCost.query.filter_by(
                            vehicle_id=veiculo_fleet.vehicle_id,
                            cost_date=custo.data_custo,
                            cost_type=custo.tipo_custo,
                            cost_amount=custo.valor
                        ).first()
                        
                        if existing:
                            logger.info(f"⚠️ Custo {custo.id} já migrado, pulando...")
                            continue
                        
                        # Criar novo registro FLEET
                        novo_custo = self.FleetVehicleCost(
                            vehicle_id=veiculo_fleet.vehicle_id,
                            cost_date=custo.data_custo,
                            cost_type=custo.tipo_custo,
                            cost_amount=custo.valor,
                            cost_description=custo.descricao,
                            supplier_name=custo.fornecedor,
                            invoice_number=custo.numero_nota_fiscal,
                            due_date=custo.data_vencimento,
                            payment_status=custo.status_pagamento or 'Pendente',
                            payment_method=custo.forma_pagamento,
                            vehicle_km=custo.km_veiculo,
                            cost_notes=custo.observacoes,
                            admin_owner_id=custo.admin_id,
                            created_at=custo.created_at,
                            updated_at=custo.updated_at
                        )
                        
                        self.db.session.add(novo_custo)
                        self.migration_stats['custos_migrados'] += 1
                        
                        if self.migration_stats['custos_migrados'] % 20 == 0:
                            self.db.session.commit()
                            logger.info(f"💰 Migrados {self.migration_stats['custos_migrados']} custos...")
                        
                    except Exception as e:
                        logger.error(f"❌ Erro ao migrar custo {custo.id}: {e}")
                        self.migration_stats['erros'].append(f"Custo {custo.id}: {e}")
                        continue
                
                self.db.session.commit()
                logger.info(f"✅ Migração de custos concluída: {self.migration_stats['custos_migrados']} registros")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro na migração de custos: {e}")
            logger.error(traceback.format_exc())
            self.db.session.rollback()
            return False
    
    def validar_migracao(self):
        """Validar se a migração foi bem-sucedida"""
        try:
            logger.info("✅ Iniciando validação da migração...")
            
            with self.app.app_context():
                # Contar registros legacy
                legacy_counts = {
                    'veiculos': self.Veiculo.query.count(),
                    'usos': self.UsoVeiculo.query.count(),
                    'custos': self.CustoVeiculo.query.count()
                }
                
                # Contar registros FLEET
                fleet_counts = {
                    'veiculos': self.FleetVehicle.query.count(),
                    'usos': self.FleetVehicleUsage.query.count(),
                    'custos': self.FleetVehicleCost.query.count()
                }
                
                logger.info("📊 COMPARAÇÃO DE REGISTROS:")
                logger.info(f"   Veículos - Legacy: {legacy_counts['veiculos']} | FLEET: {fleet_counts['veiculos']}")
                logger.info(f"   Usos - Legacy: {legacy_counts['usos']} | FLEET: {fleet_counts['usos']}")
                logger.info(f"   Custos - Legacy: {legacy_counts['custos']} | FLEET: {fleet_counts['custos']}")
                
                # Validação de integridade referencial
                orphan_usos = self.db.session.execute("""
                    SELECT COUNT(*) FROM fleet_vehicle_usage u 
                    WHERE NOT EXISTS (
                        SELECT 1 FROM fleet_vehicle v WHERE v.vehicle_id = u.vehicle_id
                    )
                """).scalar()
                
                orphan_custos = self.db.session.execute("""
                    SELECT COUNT(*) FROM fleet_vehicle_cost c 
                    WHERE NOT EXISTS (
                        SELECT 1 FROM fleet_vehicle v WHERE v.vehicle_id = c.vehicle_id
                    )
                """).scalar()
                
                logger.info(f"🔗 Usos órfãos: {orphan_usos}")
                logger.info(f"🔗 Custos órfãos: {orphan_custos}")
                
                # Determinar sucesso
                sucesso = (
                    fleet_counts['veiculos'] > 0 and
                    orphan_usos == 0 and
                    orphan_custos == 0 and
                    len(self.migration_stats['erros']) == 0
                )
                
                if sucesso:
                    logger.info("✅ VALIDAÇÃO PASSOU - Migração bem-sucedida!")
                else:
                    logger.error("❌ VALIDAÇÃO FALHOU - Problemas detectados")
                
                return {
                    'sucesso': sucesso,
                    'legacy_counts': legacy_counts,
                    'fleet_counts': fleet_counts,
                    'orphan_usos': orphan_usos,
                    'orphan_custos': orphan_custos,
                    'erros': self.migration_stats['erros']
                }
                
        except Exception as e:
            logger.error(f"❌ Erro na validação: {e}")
            logger.error(traceback.format_exc())
            return {'sucesso': False, 'erro': str(e)}
    
    def executar_migracao_completa(self):
        """Executar migração completa com todas as etapas"""
        try:
            logger.info("🚀 INICIANDO MIGRAÇÃO COMPLETA DO SISTEMA FLEET")
            logger.info("=" * 60)
            
            # Verificar ambiente
            ambiente = self.verificar_ambiente()
            
            # Verificar pré-requisitos
            prereq = self.verificar_prerequisitos()
            if not prereq.get('ready'):
                logger.error("❌ Pré-requisitos não atendidos")
                return False
            
            # Fazer backup
            backup_file = self.fazer_backup_completo()
            if not backup_file:
                logger.error("❌ Backup falhou - abortando migração")
                return False
            
            # Criar tabelas FLEET
            if not self.criar_tabelas_fleet():
                logger.error("❌ Criação de tabelas falhou - abortando migração")
                return False
            
            # Migrar dados
            logger.info("📦 Iniciando migração de dados...")
            
            if not self.migrar_veiculos():
                logger.error("❌ Migração de veículos falhou - abortando")
                return False
            
            if not self.migrar_usos():
                logger.error("❌ Migração de usos falhou - abortando")
                return False
            
            if not self.migrar_custos():
                logger.error("❌ Migração de custos falhou - abortando")
                return False
            
            # Validar migração
            validacao = self.validar_migracao()
            if not validacao['sucesso']:
                logger.error("❌ Validação falhou - migração com problemas")
                return False
            
            # Estatísticas finais
            self.migration_stats['fim'] = datetime.now()
            duracao = self.migration_stats['fim'] - self.migration_stats['inicio']
            
            logger.info("=" * 60)
            logger.info("🎉 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            logger.info(f"⏱️ Duração: {duracao}")
            logger.info(f"🚗 Veículos migrados: {self.migration_stats['veiculos_migrados']}")
            logger.info(f"🚌 Usos migrados: {self.migration_stats['usos_migrados']}")
            logger.info(f"💰 Custos migrados: {self.migration_stats['custos_migrados']}")
            logger.info(f"💾 Backup salvo em: {backup_file}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ ERRO CRÍTICO NA MIGRAÇÃO: {e}")
            logger.error(traceback.format_exc())
            return False


def main():
    """Função principal"""
    # Verificar execução automática
    auto_mode = '--auto' in sys.argv or os.environ.get('AUTO_MIGRATIONS_ENABLED') == 'true'
    
    if not auto_mode:
        print("🚨 ATENÇÃO: MIGRAÇÃO COMPLETA DO SISTEMA DE VEÍCULOS")
        print("   - Irá migrar TODOS os dados para novas tabelas FLEET")
        print("   - Fará backup automático dos dados atuais")
        print("   - Processo irreversível - use backup para rollback se necessário")
        response = input("\n🤔 Confirma execução? (digite 'CONFIRMO'): ")
        if response != 'CONFIRMO':
            print("❌ Migração cancelada pelo usuário")
            return False
    else:
        print("🚀 Executando migração automaticamente")
    
    # Executar migração
    migration = FleetMigration()
    
    if not migration.setup_flask_app():
        print("❌ Erro no setup - abortando")
        return False
    
    sucesso = migration.executar_migracao_completa()
    
    if sucesso:
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        return True
    else:
        print("❌ MIGRAÇÃO FALHOU - Verifique os logs")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)