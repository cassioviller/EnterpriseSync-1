"""
Orquestrador Saga para SIGE
Implementa padrão Saga para operações multi-etapas com compensações
"""

import uuid
import time
import json
from enum import Enum
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass, asdict
from app import db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

class SagaStatus(Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"

class StepStatus(Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"

@dataclass
class SagaStep:
    """Representa um passo da saga"""
    step_id: str
    name: str
    execute_func: Callable
    compensate_func: Callable
    data: Dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    executed_at: Optional[float] = None
    compensated_at: Optional[float] = None

class SagaOrchestrator:
    """Orquestrador de Saga para operações multi-etapas"""
    
    def __init__(self, saga_id: str = None, saga_type: str = "generic", admin_id: int = None):
        self.saga_id = saga_id or str(uuid.uuid4())
        self.saga_type = saga_type
        self.admin_id = admin_id
        self.steps: List[SagaStep] = []
        self.status = SagaStatus.STARTED
        self.started_at = time.time()
        self.completed_at = None
        self.correlation_id = f"{saga_type}_{self.saga_id[:8]}"
        
        # Garantir tabela existe
        self._ensure_saga_table()
        
        logger.info(f"🎭 Saga iniciada: {self.saga_type} | ID: {self.saga_id[:8]}... | Correlation: {self.correlation_id}")

    def _ensure_saga_table(self):
        """Cria tabelas de saga se não existirem"""
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS saga_executions (
                    id SERIAL PRIMARY KEY,
                    saga_id VARCHAR(36) UNIQUE NOT NULL,
                    saga_type VARCHAR(50) NOT NULL,
                    admin_id INTEGER,
                    status VARCHAR(20) NOT NULL,
                    correlation_id VARCHAR(100),
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    total_steps INTEGER DEFAULT 0,
                    executed_steps INTEGER DEFAULT 0,
                    compensated_steps INTEGER DEFAULT 0,
                    saga_data TEXT,
                    error_message TEXT
                );
                
                CREATE TABLE IF NOT EXISTS saga_steps (
                    id SERIAL PRIMARY KEY,
                    saga_id VARCHAR(36) NOT NULL,
                    step_id VARCHAR(100) NOT NULL,
                    step_name VARCHAR(100) NOT NULL,
                    step_order INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    step_data TEXT,
                    result_data TEXT,
                    error_message TEXT,
                    executed_at TIMESTAMP,
                    compensated_at TIMESTAMP,
                    FOREIGN KEY (saga_id) REFERENCES saga_executions(saga_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_saga_id ON saga_steps(saga_id);
                CREATE INDEX IF NOT EXISTS idx_saga_status ON saga_executions(status);
            """))
            db.session.commit()
            logger.debug("✅ Tabelas de saga criadas/verificadas")
        except Exception as e:
            logger.error(f"Erro ao criar tabelas saga: {e}")
            db.session.rollback()

    def add_step(self, name: str, execute_func: Callable, compensate_func: Callable, data: Dict[str, Any] = None) -> str:
        """
        Adiciona um passo à saga
        
        Args:
            name: Nome descritivo do passo
            execute_func: Função para executar o passo
            compensate_func: Função para compensar o passo
            data: Dados específicos do passo
            
        Returns:
            step_id: ID único do passo
        """
        step_id = f"{name}_{len(self.steps)}_{int(time.time())}"
        step = SagaStep(
            step_id=step_id,
            name=name,
            execute_func=execute_func,
            compensate_func=compensate_func,
            data=data or {}
        )
        self.steps.append(step)
        
        logger.debug(f"➕ Passo adicionado à saga {self.saga_id[:8]}...: {name}")
        return step_id

    def execute(self) -> bool:
        """
        Executa todos os passos da saga
        
        Returns:
            bool: True se todos os passos foram executados com sucesso
        """
        try:
            # Persistir saga no banco
            self._persist_saga()
            
            logger.info(f"🚀 Executando saga {self.saga_type} com {len(self.steps)} passos")
            
            for i, step in enumerate(self.steps):
                try:
                    logger.info(f"🔄 Executando passo {i+1}/{len(self.steps)}: {step.name}")
                    
                    # Executar passo
                    step.executed_at = time.time()
                    step.result = step.execute_func(**step.data)
                    step.status = StepStatus.EXECUTED
                    
                    # Persistir resultado do passo
                    self._persist_step(step, i)
                    
                    logger.info(f"✅ Passo concluído: {step.name}")
                    
                except Exception as e:
                    step.error = str(e)
                    step.status = StepStatus.FAILED
                    
                    logger.error(f"❌ Falha no passo {step.name}: {e}")
                    
                    # Persistir falha
                    self._persist_step(step, i)
                    
                    # Iniciar compensação
                    self._compensate(i)
                    return False
            
            # Todos os passos executados com sucesso
            self.status = SagaStatus.COMPLETED
            self.completed_at = time.time()
            self._update_saga_status()
            
            logger.info(f"🎉 Saga {self.saga_type} concluída com sucesso em {self.completed_at - self.started_at:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"💥 Erro crítico na saga {self.saga_type}: {e}")
            self.status = SagaStatus.FAILED
            self._update_saga_status()
            return False

    def _compensate(self, failed_step_index: int):
        """
        Executa compensação para todos os passos já executados
        
        Args:
            failed_step_index: Índice do passo que falhou
        """
        self.status = SagaStatus.COMPENSATING
        self._update_saga_status()
        
        logger.warning(f"🔄 Iniciando compensação da saga {self.saga_type}")
        
        # Compensar em ordem reversa (LIFO)
        for i in range(failed_step_index - 1, -1, -1):
            step = self.steps[i]
            
            if step.status == StepStatus.EXECUTED:
                try:
                    logger.info(f"🔄 Compensando passo: {step.name}")
                    
                    step.compensate_func(**step.data, result=step.result)
                    step.status = StepStatus.COMPENSATED
                    step.compensated_at = time.time()
                    
                    # Persistir compensação
                    self._persist_step(step, i)
                    
                    logger.info(f"✅ Compensação concluída: {step.name}")
                    
                except Exception as e:
                    logger.error(f"❌ Falha na compensação do passo {step.name}: {e}")
                    # Continuar compensando outros passos mesmo se um falhar
        
        self.status = SagaStatus.COMPENSATED
        self.completed_at = time.time()
        self._update_saga_status()
        
        logger.warning(f"🔄 Compensação da saga {self.saga_type} concluída")

    def _persist_saga(self):
        """Persiste dados da saga no banco"""
        try:
            saga_data = {
                'steps': [step.name for step in self.steps],
                'admin_id': self.admin_id,
                'correlation_id': self.correlation_id
            }
            
            db.session.execute(text("""
                INSERT INTO saga_executions 
                (saga_id, saga_type, admin_id, status, correlation_id, total_steps, saga_data)
                VALUES (:saga_id, :saga_type, :admin_id, :status, :correlation_id, :total_steps, :saga_data)
                ON CONFLICT (saga_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    total_steps = EXCLUDED.total_steps
            """), {
                'saga_id': self.saga_id,
                'saga_type': self.saga_type,
                'admin_id': self.admin_id,
                'status': self.status.value,
                'correlation_id': self.correlation_id,
                'total_steps': len(self.steps),
                'saga_data': json.dumps(saga_data)
            })
            db.session.commit()
        except Exception as e:
            logger.error(f"Erro ao persistir saga: {e}")
            db.session.rollback()

    def _persist_step(self, step: SagaStep, order: int):
        """Persiste dados do passo no banco"""
        try:
            result_data = None
            if step.result:
                try:
                    result_data = json.dumps(step.result) if isinstance(step.result, (dict, list)) else str(step.result)
                except:
                    result_data = str(step.result)
            
            db.session.execute(text("""
                INSERT INTO saga_steps 
                (saga_id, step_id, step_name, step_order, status, step_data, result_data, error_message, executed_at, compensated_at)
                VALUES (:saga_id, :step_id, :step_name, :step_order, :status, :step_data, :result_data, :error_message, 
                        :executed_at, :compensated_at)
                ON CONFLICT (saga_id, step_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    result_data = EXCLUDED.result_data,
                    error_message = EXCLUDED.error_message,
                    executed_at = EXCLUDED.executed_at,
                    compensated_at = EXCLUDED.compensated_at
            """), {
                'saga_id': self.saga_id,
                'step_id': step.step_id,
                'step_name': step.name,
                'step_order': order,
                'status': step.status.value,
                'step_data': json.dumps(step.data),
                'result_data': result_data,
                'error_message': step.error,
                'executed_at': time.time() if step.executed_at else None,
                'compensated_at': time.time() if step.compensated_at else None
            })
            db.session.commit()
        except Exception as e:
            logger.error(f"Erro ao persistir passo da saga: {e}")
            db.session.rollback()

    def _update_saga_status(self):
        """Atualiza status da saga no banco"""
        try:
            executed_steps = sum(1 for step in self.steps if step.status == StepStatus.EXECUTED)
            compensated_steps = sum(1 for step in self.steps if step.status == StepStatus.COMPENSATED)
            
            db.session.execute(text("""
                UPDATE saga_executions SET
                    status = :status,
                    completed_at = :completed_at,
                    executed_steps = :executed_steps,
                    compensated_steps = :compensated_steps
                WHERE saga_id = :saga_id
            """), {
                'saga_id': self.saga_id,
                'status': self.status.value,
                'completed_at': time.time() if self.completed_at else None,
                'executed_steps': executed_steps,
                'compensated_steps': compensated_steps
            })
            db.session.commit()
        except Exception as e:
            logger.error(f"Erro ao atualizar status da saga: {e}")
            db.session.rollback()

    def get_status(self) -> Dict[str, Any]:
        """Retorna status detalhado da saga"""
        return {
            'saga_id': self.saga_id,
            'saga_type': self.saga_type,
            'status': self.status.value,
            'correlation_id': self.correlation_id,
            'total_steps': len(self.steps),
            'executed_steps': sum(1 for step in self.steps if step.status == StepStatus.EXECUTED),
            'compensated_steps': sum(1 for step in self.steps if step.status == StepStatus.COMPENSATED),
            'failed_steps': sum(1 for step in self.steps if step.status == StepStatus.FAILED),
            'duration': (self.completed_at or time.time()) - self.started_at,
            'steps': [
                {
                    'name': step.name,
                    'status': step.status.value,
                    'error': step.error,
                    'executed_at': step.executed_at,
                    'compensated_at': step.compensated_at
                }
                for step in self.steps
            ]
        }

# Sagas específicas do SIGE

class RDOSaga:
    """Saga específica para criação/edição de RDO"""
    
    def __init__(self, admin_id: int, obra_id: int, data_relatorio: str):
        self.saga = SagaOrchestrator(
            saga_type="rdo_creation",
            admin_id=admin_id
        )
        self.obra_id = obra_id
        self.data_relatorio = data_relatorio
        self.rdo_id = None

    def create_rdo_workflow(self, rdo_data: Dict[str, Any]) -> bool:
        """
        Workflow completo de criação de RDO
        """
        # Passo 1: Criar RDO base
        self.saga.add_step(
            "create_rdo",
            self._create_rdo_step,
            self._compensate_rdo_step,
            {"rdo_data": rdo_data}
        )
        
        # Passo 2: Adicionar serviços
        if rdo_data.get('servicos'):
            self.saga.add_step(
                "add_services",
                self._add_services_step,
                self._compensate_services_step,
                {"servicos": rdo_data['servicos']}
            )
        
        # Passo 3: Calcular custos
        self.saga.add_step(
            "calculate_costs",
            self._calculate_costs_step,
            self._compensate_costs_step,
            {"rdo_data": rdo_data}
        )
        
        # Passo 4: Finalizar RDO
        self.saga.add_step(
            "finalize_rdo",
            self._finalize_rdo_step,
            self._compensate_finalize_step,
            {}
        )
        
        return self.saga.execute()

    def _create_rdo_step(self, rdo_data: Dict[str, Any]) -> int:
        """Cria RDO no banco de dados"""
        from models import RDO
        
        rdo = RDO(
            obra_id=self.obra_id,
            data_relatorio=self.data_relatorio,
            admin_id=self.saga.admin_id,
            status='Rascunho',
            **rdo_data
        )
        
        db.session.add(rdo)
        db.session.flush()  # Obter ID sem commit
        
        self.rdo_id = rdo.id
        logger.info(f"RDO criado com ID: {self.rdo_id}")
        return self.rdo_id

    def _compensate_rdo_step(self, rdo_data: Dict[str, Any], result: int = None):
        """Compensa criação do RDO"""
        if result:  # result é o rdo_id
            from models import RDO
            rdo = RDO.query.get(result)
            if rdo:
                db.session.delete(rdo)
                db.session.flush()
                logger.info(f"RDO {result} removido (compensação)")

    def _add_services_step(self, servicos: List[Dict]) -> List[int]:
        """Adiciona serviços ao RDO"""
        from models import RDOServicoSubatividade
        
        service_ids = []
        for servico in servicos:
            rdo_servico = RDOServicoSubatividade(
                rdo_id=self.rdo_id,
                **servico
            )
            db.session.add(rdo_servico)
            db.session.flush()
            service_ids.append(rdo_servico.id)
        
        logger.info(f"{len(service_ids)} serviços adicionados ao RDO {self.rdo_id}")
        return service_ids

    def _compensate_services_step(self, servicos: List[Dict], result: List[int] = None):
        """Compensa adição de serviços"""
        if result:  # result é lista de service_ids
            from models import RDOServicoSubatividade
            for service_id in result:
                service = RDOServicoSubatividade.query.get(service_id)
                if service:
                    db.session.delete(service)
            db.session.flush()
            logger.info(f"{len(result)} serviços removidos (compensação)")

    def _calculate_costs_step(self, rdo_data: Dict[str, Any]) -> Dict[str, float]:
        """Calcula custos do RDO"""
        # Implementar cálculo de custos
        costs = {
            'mao_obra': 0.0,
            'materiais': 0.0,
            'equipamentos': 0.0,
            'total': 0.0
        }
        
        # Simular cálculo (implementar lógica real)
        costs['total'] = sum(costs.values())
        
        # Salvar custos no RDO
        from models import RDO
        rdo = RDO.query.get(self.rdo_id)
        if rdo:
            rdo.custo_total = costs['total']
            db.session.flush()
        
        logger.info(f"Custos calculados para RDO {self.rdo_id}: R$ {costs['total']:.2f}")
        return costs

    def _compensate_costs_step(self, rdo_data: Dict[str, Any], result: Dict[str, float] = None):
        """Compensa cálculo de custos"""
        if self.rdo_id:
            from models import RDO
            rdo = RDO.query.get(self.rdo_id)
            if rdo:
                rdo.custo_total = 0.0
                db.session.flush()
                logger.info(f"Custos zerados para RDO {self.rdo_id} (compensação)")

    def _finalize_rdo_step(self) -> bool:
        """Finaliza RDO mudando status"""
        from models import RDO
        rdo = RDO.query.get(self.rdo_id)
        if rdo:
            rdo.status = 'Finalizado'
            db.session.flush()
            logger.info(f"RDO {self.rdo_id} finalizado")
            return True
        return False

    def _compensate_finalize_step(self, result: bool = None):
        """Compensa finalização do RDO"""
        if self.rdo_id and result:
            from models import RDO
            rdo = RDO.query.get(self.rdo_id)
            if rdo:
                rdo.status = 'Rascunho'
                db.session.flush()
                logger.info(f"RDO {self.rdo_id} revertido para rascunho (compensação)")

class FuncionarioSaga:
    """Saga para operações críticas de funcionários"""
    
    def __init__(self, admin_id: int, funcionario_id: int):
        self.saga = SagaOrchestrator(
            saga_type="funcionario_operation",
            admin_id=admin_id
        )
        self.funcionario_id = funcionario_id

    def update_salary_workflow(self, novo_salario: float, justificativa: str) -> bool:
        """Workflow de atualização salarial com auditoria"""
        
        # Passo 1: Backup do salário atual
        self.saga.add_step(
            "backup_salary",
            self._backup_salary_step,
            self._restore_salary_step,
            {"funcionario_id": self.funcionario_id}
        )
        
        # Passo 2: Atualizar salário
        self.saga.add_step(
            "update_salary",
            self._update_salary_step,
            self._revert_salary_step,
            {
                "funcionario_id": self.funcionario_id,
                "novo_salario": novo_salario
            }
        )
        
        # Passo 3: Registrar auditoria
        self.saga.add_step(
            "audit_log",
            self._audit_log_step,
            self._remove_audit_step,
            {
                "funcionario_id": self.funcionario_id,
                "novo_salario": novo_salario,
                "justificativa": justificativa
            }
        )
        
        return self.saga.execute()

    def _backup_salary_step(self, funcionario_id: int) -> float:
        """Faz backup do salário atual"""
        from models import Funcionario
        funcionario = Funcionario.query.get(funcionario_id)
        if funcionario:
            return funcionario.salario or 0.0
        return 0.0

    def _restore_salary_step(self, funcionario_id: int, result: float = None):
        """Restaura salário do backup"""
        if result is not None:
            from models import Funcionario
            funcionario = Funcionario.query.get(funcionario_id)
            if funcionario:
                funcionario.salario = result
                db.session.flush()

    def _update_salary_step(self, funcionario_id: int, novo_salario: float) -> float:
        """Atualiza salário do funcionário"""
        from models import Funcionario
        funcionario = Funcionario.query.get(funcionario_id)
        if funcionario:
            old_salary = funcionario.salario
            funcionario.salario = novo_salario
            db.session.flush()
            return old_salary
        return 0.0

    def _revert_salary_step(self, funcionario_id: int, novo_salario: float, result: float = None):
        """Reverte atualização salarial"""
        if result is not None:
            from models import Funcionario
            funcionario = Funcionario.query.get(funcionario_id)
            if funcionario:
                funcionario.salario = result
                db.session.flush()

    def _audit_log_step(self, funcionario_id: int, novo_salario: float, justificativa: str) -> int:
        """Registra log de auditoria"""
        # Implementar modelo de auditoria se necessário
        logger.info(f"Auditoria: Funcionário {funcionario_id} - Novo salário: R$ {novo_salario:.2f} - {justificativa}")
        return 1  # ID fictício do log

    def _remove_audit_step(self, funcionario_id: int, novo_salario: float, justificativa: str, result: int = None):
        """Remove log de auditoria"""
        if result:
            logger.info(f"Auditoria removida: ID {result} (compensação)")

# Utilitários para monitoramento de sagas

def get_saga_status(saga_id: str) -> Optional[Dict[str, Any]]:
    """Obtém status de uma saga pelo ID"""
    try:
        result = db.session.execute(text("""
            SELECT saga_type, status, correlation_id, started_at, completed_at,
                   total_steps, executed_steps, compensated_steps, error_message
            FROM saga_executions 
            WHERE saga_id = :saga_id
        """), {'saga_id': saga_id}).fetchone()
        
        if result:
            return {
                'saga_id': saga_id,
                'saga_type': result[0],
                'status': result[1],
                'correlation_id': result[2],
                'started_at': result[3],
                'completed_at': result[4],
                'total_steps': result[5],
                'executed_steps': result[6],
                'compensated_steps': result[7],
                'error_message': result[8]
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar status da saga: {e}")
        return None

def list_active_sagas(admin_id: int = None) -> List[Dict[str, Any]]:
    """Lista sagas ativas (não concluídas)"""
    try:
        query = """
            SELECT saga_id, saga_type, status, correlation_id, started_at,
                   total_steps, executed_steps
            FROM saga_executions 
            WHERE status IN ('STARTED', 'COMPENSATING')
        """
        params = {}
        
        if admin_id:
            query += " AND admin_id = :admin_id"
            params['admin_id'] = admin_id
            
        query += " ORDER BY started_at DESC"
        
        results = db.session.execute(text(query), params).fetchall()
        
        return [
            {
                'saga_id': row[0],
                'saga_type': row[1],
                'status': row[2],
                'correlation_id': row[3],
                'started_at': row[4],
                'total_steps': row[5],
                'executed_steps': row[6]
            }
            for row in results
        ]
    except Exception as e:
        logger.error(f"Erro ao listar sagas ativas: {e}")
        return []

def cleanup_old_sagas(days_old: int = 30):
    """Remove sagas antigas do banco"""
    try:
        result = db.session.execute(text("""
            DELETE FROM saga_executions 
            WHERE started_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
            AND status IN ('COMPLETED', 'FAILED', 'COMPENSATED')
        """ % days_old))
        
        deleted = result.rowcount
        db.session.commit()
        
        if deleted > 0:
            logger.info(f"🧹 Limpeza: {deleted} sagas antigas removidas")
    except Exception as e:
        logger.error(f"Erro na limpeza de sagas: {e}")
        db.session.rollback()