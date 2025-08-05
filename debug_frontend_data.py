#!/usr/bin/env python3
"""
DEBUG: Verificar se há valores padrão sendo aplicados no frontend
Adicionar logs JavaScript para capturar exatamente o que está sendo enviado
"""

def adicionar_debug_javascript():
    """Adiciona JavaScript de debug no template de alimentação"""
    
    print("🔧 ADICIONANDO DEBUG JAVASCRIPT")
    print("=" * 50)
    
    # JavaScript para adicionar ao template
    debug_js = '''
// DEBUG: Interceptar envio do formulário
document.getElementById('alimentacaoForm').addEventListener('submit', function(e) {
    console.log('🔍 DEBUG: Formulário sendo enviado');
    
    // Capturar todos os valores dos campos de data
    const dataUnica = document.getElementById('data').value;
    const dataInicio = document.getElementById('data_inicio').value;
    const dataFim = document.getElementById('data_fim').value;
    
    console.log('📅 Valores capturados:');
    console.log('   data única:', dataUnica);
    console.log('   data início:', dataInicio);
    console.log('   data fim:', dataFim);
    
    // Verificar se há alteração nos valores
    const formData = new FormData(this);
    console.log('📤 FormData sendo enviado:');
    for (let [key, value] of formData.entries()) {
        if (key.includes('data')) {
            console.log(`   ${key}: ${value}`);
        }
    }
    
    // Não impedir o envio, apenas logar
});

// DEBUG: Monitorar mudanças nos campos de data
document.getElementById('data').addEventListener('change', function() {
    console.log('📅 Data única alterada para:', this.value);
});

document.getElementById('data_inicio').addEventListener('change', function() {
    console.log('📅 Data início alterada para:', this.value);
});

document.getElementById('data_fim').addEventListener('change', function() {
    console.log('📅 Data fim alterada para:', this.value);
});
'''
    
    print("JavaScript de debug criado:")
    print(debug_js)
    
    return debug_js

def verificar_valores_default():
    """Verifica se há valores padrão sendo aplicados"""
    
    print("\n🔍 VERIFICAÇÃO: Valores Padrão")
    print("-" * 40)
    
    # Casos suspeitos
    casos = [
        "Campo pode estar recebendo data atual automaticamente",
        "JavaScript pode estar alterando valor após seleção do usuário",
        "Problema de timezone do navegador",
        "Input date pode ter valor mínimo/máximo que força mudança",
        "Formulário pode ter evento que altera datas"
    ]
    
    for i, caso in enumerate(casos, 1):
        print(f"{i}. {caso}")

def simular_problema_comum():
    """Simula problemas comuns com date inputs"""
    
    print("\n⚠️ PROBLEMAS COMUNS COM DATE INPUTS:")
    print("-" * 40)
    
    from datetime import date
    
    # Data de hoje (agosto)
    hoje = date.today()
    print(f"Data atual: {hoje} (mês {hoje.month})")
    
    # Data que o usuário quer (julho)  
    data_desejada = date(2025, 7, 15)
    print(f"Data desejada: {data_desejada} (mês {data_desejada.month})")
    
    # Verificar se há lógica que substitui por data atual
    print("\nPossíveis causas:")
    print("1. JavaScript aplicando Date.now() ou new Date()")
    print("2. Campo date sem valor sendo preenchido com hoje")
    print("3. Validação que força data mínima = hoje")
    print("4. Timezone do navegador alterando a data")

if __name__ == "__main__":
    debug_js = adicionar_debug_javascript()
    verificar_valores_default()
    simular_problema_comum()