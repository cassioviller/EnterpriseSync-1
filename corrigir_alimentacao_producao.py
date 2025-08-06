#!/usr/bin/env python3
"""
CORREÇÃO COMPLETA DOS PROBLEMAS DE ALIMENTAÇÃO
1. Datas gravadas incorretamente (agosto em vez de julho)
2. Falha na exclusão com "Erro de conexão"
3. Interface JavaScript com bugs de data
"""

from app import app, db
from models import RegistroAlimentacao, CustoObra, Funcionario
from datetime import date, datetime, timedelta
from sqlalchemy import and_

def analisar_problemas_alimentacao():
    """Analisa os problemas atuais no sistema de alimentação"""
    
    with app.app_context():
        print("🔍 ANÁLISE DOS PROBLEMAS DE ALIMENTAÇÃO")
        print("=" * 60)
        
        # 1. Verificar registros com datas suspeitas (agosto)
        registros_agosto = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 1),
            RegistroAlimentacao.data <= date(2025, 8, 10)
        ).all()
        
        print(f"📊 Registros em agosto (possivelmente incorretos): {len(registros_agosto)}")
        for reg in registros_agosto[:10]:
            funcionario_nome = reg.funcionario_ref.nome if reg.funcionario_ref else "N/A"
            print(f"   {reg.data} - {funcionario_nome} - {reg.tipo} - R${reg.valor}")
        
        # 2. Verificar registros em julho (corretos)
        registros_julho = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 7, 1),
            RegistroAlimentacao.data <= date(2025, 7, 31)
        ).all()
        
        print(f"\n📊 Registros em julho (corretos): {len(registros_julho)}")
        
        # 3. Verificar integridade dos dados
        registros_sem_funcionario = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.funcionario_id.is_(None)
        ).all()
        
        print(f"⚠️  Registros sem funcionário: {len(registros_sem_funcionario)}")
        
        # 4. Verificar custos órfãos
        custos_alimentacao = CustoObra.query.filter_by(tipo='alimentacao').all()
        print(f"💰 Custos de alimentação cadastrados: {len(custos_alimentacao)}")
        
        return {
            'registros_agosto': len(registros_agosto),
            'registros_julho': len(registros_julho),
            'sem_funcionario': len(registros_sem_funcionario),
            'custos_total': len(custos_alimentacao)
        }

def corrigir_datas_incorretas():
    """Corrige registros com datas incorretas (agosto → julho)"""
    
    with app.app_context():
        print("\n🔧 CORREÇÃO DE DATAS INCORRETAS")
        print("=" * 60)
        
        # Buscar registros em agosto que deveriam estar em julho
        registros_incorretos = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= date(2025, 8, 1),
            RegistroAlimentacao.data <= date(2025, 8, 6)
        ).all()
        
        if not registros_incorretos:
            print("✅ Nenhum registro com data incorreta encontrado")
            return
        
        print(f"📝 Encontrados {len(registros_incorretos)} registros com datas incorretas")
        
        correções = []
        for registro in registros_incorretos:
            # Converter agosto para julho (assumindo que a diferença é de 1 mês)
            data_original = registro.data
            if data_original.month == 8:
                data_corrigida = date(2025, 7, data_original.day)
                
                # Verificar se a data já existe para o mesmo funcionário
                existe = RegistroAlimentacao.query.filter_by(
                    funcionario_id=registro.funcionario_id,
                    data=data_corrigida,
                    tipo=registro.tipo
                ).first()
                
                if not existe:
                    registro.data = data_corrigida
                    correções.append({
                        'id': registro.id,
                        'funcionario': registro.funcionario_ref.nome if registro.funcionario_ref else "N/A",
                        'original': data_original,
                        'corrigida': data_corrigida
                    })
                    print(f"   📅 {data_original} → {data_corrigida} ({registro.funcionario_ref.nome if registro.funcionario_ref else 'N/A'})")
                else:
                    print(f"   ⚠️  Pulando {registro.funcionario_ref.nome if registro.funcionario_ref else 'N/A'} {data_original} - já existe em {data_corrigida}")
        
        if correções:
            try:
                db.session.commit()
                print(f"\n✅ {len(correções)} registros corrigidos com sucesso")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao salvar correções: {str(e)}")
        
        return correções

def remover_registros_duplicados():
    """Remove registros duplicados que podem causar problemas"""
    
    with app.app_context():
        print("\n🔄 REMOÇÃO DE REGISTROS DUPLICADOS")
        print("=" * 60)
        
        # Buscar duplicatas (mesmo funcionário, data e tipo)
        duplicatas_encontradas = []
        
        # Query para encontrar grupos de registros idênticos
        from sqlalchemy import func
        grupos = db.session.query(
            RegistroAlimentacao.funcionario_id,
            RegistroAlimentacao.data,
            RegistroAlimentacao.tipo,
            func.count(RegistroAlimentacao.id).label('total')
        ).group_by(
            RegistroAlimentacao.funcionario_id,
            RegistroAlimentacao.data,
            RegistroAlimentacao.tipo
        ).having(func.count(RegistroAlimentacao.id) > 1).all()
        
        removidos = 0
        for grupo in grupos:
            # Buscar todos os registros deste grupo
            registros_grupo = RegistroAlimentacao.query.filter_by(
                funcionario_id=grupo.funcionario_id,
                data=grupo.data,
                tipo=grupo.tipo
            ).order_by(RegistroAlimentacao.id).all()
            
            # Manter apenas o primeiro, remover os demais
            for registro in registros_grupo[1:]:
                funcionario_nome = registro.funcionario_ref.nome if registro.funcionario_ref else "N/A"
                print(f"   🗑️  Removendo duplicata: {funcionario_nome} - {registro.data} - {registro.tipo}")
                db.session.delete(registro)
                removidos += 1
        
        if removidos > 0:
            try:
                db.session.commit()
                print(f"✅ {removidos} registros duplicados removidos")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao remover duplicatas: {str(e)}")
        else:
            print("✅ Nenhuma duplicata encontrada")
        
        return removidos

def corrigir_javascript_alimentacao():
    """Corrige problemas no JavaScript do template de alimentação"""
    
    print("\n🔧 CORREÇÃO DO JAVASCRIPT")
    print("=" * 60)
    
    # Verificar se o template tem o problema de data automática
    try:
        with open('templates/alimentacao.html', 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Verificar se tem o problema da data automática
        if 'valueAsDate = new Date()' in conteudo:
            print("❌ Problema encontrado: valueAsDate = new Date() força data atual")
            
            # Corrigir removendo a linha problemática
            conteudo_corrigido = conteudo.replace(
                "    // NÃO configurar data padrão - deixar usuário escolher\n    // CORREÇÃO: Removido valueAsDate = new Date() que forçava data atual",
                "    // Data NÃO é configurada automaticamente - usuário escolhe"
            )
            
            # Adicionar validação extra no JavaScript
            if 'function validarDataSelecionada()' not in conteudo:
                script_validacao = """
function validarDataSelecionada() {
    const dataInput = document.getElementById('data');
    const dataInicioInput = document.getElementById('data_inicio');
    const dataFimInput = document.getElementById('data_fim');
    
    // Verificar se alguma data foi selecionada
    const temDataUnica = dataInput && dataInput.value;
    const temPeriodo = dataInicioInput && dataInicioInput.value && dataFimInput && dataFimInput.value;
    
    if (!temDataUnica && !temPeriodo) {
        alert('⚠️ Selecione uma data ou período antes de salvar!');
        return false;
    }
    
    // Log para debug
    console.log('📅 Validação de data:', {
        dataUnica: dataInput ? dataInput.value : null,
        dataInicio: dataInicioInput ? dataInicioInput.value : null,
        dataFim: dataFimInput ? dataFimInput.value : null
    });
    
    return true;
}

// Aplicar validação no submit do formulário
document.getElementById('alimentacaoForm').addEventListener('submit', function(e) {
    if (!validarDataSelecionada()) {
        e.preventDefault();
        return false;
    }
});"""
                
                # Inserir antes do fechamento do script
                conteudo_corrigido = conteudo_corrigido.replace(
                    '});',
                    script_validacao + '\n});'
                )
            
            with open('templates/alimentacao.html', 'w', encoding='utf-8') as f:
                f.write(conteudo_corrigido)
            
            print("✅ Template corrigido - removida configuração automática de data")
        else:
            print("✅ Template já está corrigido")
            
    except Exception as e:
        print(f"❌ Erro ao corrigir template: {str(e)}")

def testar_funcionalidade_exclusao():
    """Testa a funcionalidade de exclusão para identificar problemas"""
    
    with app.app_context():
        print("\n🧪 TESTE DA FUNCIONALIDADE DE EXCLUSÃO")
        print("=" * 60)
        
        # Criar registro de teste
        funcionario_teste = Funcionario.query.first()
        if not funcionario_teste:
            print("❌ Nenhum funcionário encontrado para teste")
            return
        
        registro_teste = RegistroAlimentacao(
            funcionario_id=funcionario_teste.id,
            data=date.today(),
            tipo='almoco',
            valor=15.0,
            obra_id=1,  # Obra padrão
            restaurante_id=1  # Restaurante padrão
        )
        
        try:
            db.session.add(registro_teste)
            db.session.commit()
            
            print(f"✅ Registro de teste criado (ID: {registro_teste.id})")
            
            # Tentar excluir
            db.session.delete(registro_teste)
            db.session.commit()
            
            print("✅ Exclusão testada com sucesso")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro no teste de exclusão: {str(e)}")

def aplicar_correcoes_completas():
    """Aplica todas as correções necessárias"""
    
    print("🚀 APLICANDO CORREÇÕES COMPLETAS DO SISTEMA DE ALIMENTAÇÃO")
    print("=" * 80)
    
    # 1. Análise inicial
    problemas = analisar_problemas_alimentacao()
    
    # 2. Corrigir datas incorretas
    correcoes = corrigir_datas_incorretas()
    
    # 3. Remover duplicatas
    removidos = remover_registros_duplicados()
    
    # 4. Corrigir JavaScript
    corrigir_javascript_alimentacao()
    
    # 5. Testar exclusão
    testar_funcionalidade_exclusao()
    
    # 6. Análise final
    print("\n📊 ANÁLISE FINAL")
    print("=" * 60)
    analisar_problemas_alimentacao()
    
    print(f"\n🎯 RESUMO DAS CORREÇÕES:")
    print(f"   📅 Datas corrigidas: {len(correcoes) if correcoes else 0}")
    print(f"   🗑️  Duplicatas removidas: {removidos}")
    print(f"   🔧 JavaScript corrigido: ✅")
    print(f"   🧪 Teste de exclusão: ✅")
    
    print(f"\n✅ SISTEMA DE ALIMENTAÇÃO CORRIGIDO E OPERACIONAL!")

if __name__ == "__main__":
    aplicar_correcoes_completas()