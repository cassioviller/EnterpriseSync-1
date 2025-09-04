"""
Sistema de Observabilidade Digital Mastery
Baseado nos princípios de Joris Kuypers: maestria, controle e excelência técnica
"""
import time
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps
from collections import defaultdict, deque
import threading

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class DigitalMasteryObserver:
    """
    Sistema de observabilidade completo para RDO
    Implementa métricas, logging estruturado e monitoramento em tempo real
    """
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.operations = {}
        self.performance_data = deque(maxlen=1000)
        self.error_patterns = defaultdict(int)
        self.success_rate = defaultdict(lambda: {'total': 0, 'success': 0})
        self.lock = threading.Lock()
        self.logger = logging.getLogger('RDO_MASTERY')
        
    def start_operation(self, operation_id: str, operation_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Inicia uma operação com contexto completo"""
        timestamp = datetime.now()
        
        operation_context = {
            'operation_id': operation_id,
            'operation_type': operation_type,
            'start_time': timestamp,
            'context': context,
            'steps': [],
            'metrics': {},
            'status': 'STARTED'
        }
        
        with self.lock:
            self.operations[operation_id] = operation_context
            
        self.logger.info(f"🚀 [MASTERY:{operation_id}] {operation_type}_STARTED", extra={
            'operation_id': operation_id,
            'operation_type': operation_type,
            'context': context,
            'timestamp': timestamp.isoformat()
        })
        
        return operation_context
    
    def add_step(self, operation_id: str, step_name: str, step_data: Dict[str, Any], duration_ms: float = None):
        """Adiciona um step à operação com métricas detalhadas"""
        if operation_id not in self.operations:
            return
            
        step = {
            'step_name': step_name,
            'timestamp': datetime.now().isoformat(),
            'data': step_data,
            'duration_ms': duration_ms
        }
        
        with self.lock:
            self.operations[operation_id]['steps'].append(step)
            
        # Log estruturado para cada step
        log_level = 'INFO'
        if 'error' in step_data or 'exception' in step_data:
            log_level = 'ERROR'
        elif 'warning' in step_data:
            log_level = 'WARNING'
            
        self.logger.log(
            getattr(logging, log_level),
            f"🔧 [STEP:{operation_id}] {step_name}",
            extra=step
        )
    
    def add_metric(self, operation_id: str, metric_name: str, value: Any, tags: Dict[str, str] = None):
        """Adiciona métrica específica à operação"""
        metric = {
            'operation_id': operation_id,
            'metric_name': metric_name,
            'value': value,
            'tags': tags or {},
            'timestamp': datetime.now().isoformat()
        }
        
        with self.lock:
            self.metrics[metric_name].append(metric)
            if operation_id in self.operations:
                self.operations[operation_id]['metrics'][metric_name] = value
    
    def finish_operation(self, operation_id: str, status: str, result: Dict[str, Any] = None, error: Exception = None):
        """Finaliza operação com resultado completo"""
        if operation_id not in self.operations:
            return
            
        end_time = datetime.now()
        operation = self.operations[operation_id]
        duration_ms = (end_time - operation['start_time']).total_seconds() * 1000
        
        # Atualizar status da operação
        operation.update({
            'status': status,
            'end_time': end_time,
            'duration_ms': duration_ms,
            'result': result,
            'error': str(error) if error else None,
            'error_traceback': traceback.format_exc() if error else None
        })
        
        # Métricas de performance
        self.performance_data.append({
            'operation_id': operation_id,
            'operation_type': operation['operation_type'],
            'duration_ms': duration_ms,
            'status': status,
            'timestamp': end_time.isoformat(),
            'steps_count': len(operation['steps'])
        })
        
        # Métricas de sucesso
        op_type = operation['operation_type']
        with self.lock:
            self.success_rate[op_type]['total'] += 1
            if status == 'SUCCESS':
                self.success_rate[op_type]['success'] += 1
            else:
                self.error_patterns[f"{op_type}_{status}"] += 1
        
        # Log final
        log_level = 'INFO' if status == 'SUCCESS' else 'ERROR'
        self.logger.log(
            getattr(logging, log_level),
            f"🏁 [MASTERY:{operation_id}] {operation['operation_type']}_{status} ({duration_ms:.2f}ms)",
            extra={
                'operation_id': operation_id,
                'duration_ms': duration_ms,
                'status': status,
                'steps_count': len(operation['steps']),
                'result': result,
                'error': str(error) if error else None
            }
        )
    
    def get_operation_details(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Retorna detalhes completos de uma operação"""
        return self.operations.get(operation_id)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Retorna resumo de performance das operações"""
        if not self.performance_data:
            return {}
            
        operations = list(self.performance_data)
        
        # Calcular estatísticas
        durations = [op['duration_ms'] for op in operations]
        success_ops = [op for op in operations if op['status'] == 'SUCCESS']
        
        summary = {
            'total_operations': len(operations),
            'success_operations': len(success_ops),
            'success_rate_percent': (len(success_ops) / len(operations)) * 100 if operations else 0,
            'avg_duration_ms': sum(durations) / len(durations) if durations else 0,
            'min_duration_ms': min(durations) if durations else 0,
            'max_duration_ms': max(durations) if durations else 0,
            'last_24h': [op for op in operations if (datetime.now() - datetime.fromisoformat(op['timestamp'].replace('Z', '+00:00'))).days < 1],
            'operation_types': defaultdict(int)
        }
        
        for op in operations:
            summary['operation_types'][op['operation_type']] += 1
            
        return summary
    
    def get_error_analysis(self) -> Dict[str, Any]:
        """Analisa padrões de erro para insights"""
        with self.lock:
            return {
                'error_patterns': dict(self.error_patterns),
                'success_rates': {
                    op_type: {
                        'success_rate': (data['success'] / data['total']) * 100 if data['total'] > 0 else 0,
                        'total_operations': data['total'],
                        'successful_operations': data['success']
                    } for op_type, data in self.success_rate.items()
                }
            }

# Instância global do observador
mastery_observer = DigitalMasteryObserver()

def observe_operation(operation_type: str):
    """
    Decorator para observabilidade automática de operações
    Implementa o princípio "Kaipa da primeira vez certo" de Joris Kuypers
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import uuid
            operation_id = str(uuid.uuid4())[:8]
            
            # Capturar contexto da função
            context = {
                'function_name': func.__name__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys()) if kwargs else [],
                'module': func.__module__
            }
            
            # Iniciar observação
            operation = mastery_observer.start_operation(operation_id, operation_type, context)
            
            try:
                # Executar função com timing
                start_time = time.time()
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Adicionar métricas de performance
                mastery_observer.add_metric(operation_id, 'execution_time_ms', duration_ms)
                mastery_observer.add_step(operation_id, 'EXECUTION_COMPLETED', {
                    'duration_ms': duration_ms,
                    'result_type': type(result).__name__
                }, duration_ms)
                
                # Finalizar com sucesso
                mastery_observer.finish_operation(operation_id, 'SUCCESS', {
                    'result_summary': str(result)[:200] if result else None
                })
                
                return result
                
            except Exception as e:
                # Capturar erro com contexto completo
                error_context = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'function_name': func.__name__
                }
                
                mastery_observer.add_step(operation_id, 'ERROR_OCCURRED', error_context)
                mastery_observer.finish_operation(operation_id, 'ERROR', error=e)
                
                # Re-propagar erro
                raise
                
        return wrapper
    return decorator

def get_debug_dashboard_data() -> Dict[str, Any]:
    """
    Retorna dados completos para dashboard de debug
    Implementa visibilidade total do sistema
    """
    return {
        'performance_summary': mastery_observer.get_performance_summary(),
        'error_analysis': mastery_observer.get_error_analysis(),
        'recent_operations': [
            mastery_observer.get_operation_details(op_id) 
            for op_id in list(mastery_observer.operations.keys())[-10:]
        ],
        'system_health': {
            'total_operations_tracked': len(mastery_observer.operations),
            'metrics_collected': len(mastery_observer.metrics),
            'performance_samples': len(mastery_observer.performance_data),
            'error_patterns_detected': len(mastery_observer.error_patterns)
        }
    }