#!/usr/bin/env python3
"""
HOTFIX CRÍTICO: Corrigir JavaScript do template de alimentação
Remove códigos duplicados e corrige função de exclusão
"""

def corrigir_template_alimentacao():
    """Corrige o template de alimentação removendo duplicações e bugs"""
    
    # Template JavaScript corrigido
    script_corrigido = '''
function excluirRegistro(id) {
    if (confirm('Tem certeza que deseja excluir este registro?')) {
        // Mostrar loading
        const btn = event.target.closest('button');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        btn.disabled = true;
        
        fetch(`/alimentacao/${id}/excluir`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({})
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Remover a linha da tabela
                const row = document.getElementById(`registro-${id}`);
                if (row) {
                    row.remove();
                }
                showToast('Registro excluído com sucesso!', 'success');
                
                // Atualizar contadores se existirem
                setTimeout(() => {
                    location.reload();
                }, 1000);
            } else {
                showToast('Erro ao excluir: ' + (data.message || 'Erro desconhecido'), 'error');
                // Restaurar botão
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Erro na exclusão:', error);
            showToast('Erro de conexão: ' + error.message, 'error');
            // Restaurar botão
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        });
    }
}

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
'''
    
    try:
        # Ler o template atual
        with open('templates/alimentacao.html', 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Encontrar onde começa o script problemático
        inicio_script = conteudo.find('function excluirRegistro(id) {')
        
        if inicio_script == -1:
            print("❌ Função excluirRegistro não encontrada")
            return False
        
        # Encontrar o final do script (fechamento da tag script)
        fim_script = conteudo.find('</script>', inicio_script)
        
        if fim_script == -1:
            print("❌ Fechamento do script não encontrado")
            return False
        
        # Substituir toda a seção problemática
        conteudo_novo = (
            conteudo[:inicio_script] + 
            script_corrigido +
            '\n</script>\n{% endblock %}'
        )
        
        # Remover qualquer duplicação de {% endblock %}
        conteudo_novo = conteudo_novo.replace('{% endblock %}{% endblock %}', '{% endblock %}')
        
        # Salvar o arquivo corrigido
        with open('templates/alimentacao.html', 'w', encoding='utf-8') as f:
            f.write(conteudo_novo)
        
        print("✅ Template de alimentação corrigido com sucesso")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao corrigir template: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 HOTFIX: Corrigindo JavaScript do template de alimentação")
    print("=" * 60)
    
    if corrigir_template_alimentacao():
        print("✅ Correção aplicada com sucesso!")
        print("🔄 Reinicie o servidor para aplicar as mudanças")
    else:
        print("❌ Falha na correção")