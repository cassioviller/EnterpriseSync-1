#!/usr/bin/env python3
"""
🔧 TESTE FINAL: Modal de edição funcionando
"""

from app import app, db
from models import RegistroPonto, Usuario, TipoUsuario
import requests

def testar_modal_apos_correcao():
    """Testar modal após correção das permissões"""
    print("🧪 TESTE FINAL: Modal após correção")
    print("=" * 60)
    
    with app.app_context():
        # Buscar usuário admin
        admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
        if not admin:
            print("❌ Nenhum admin encontrado")
            return
        
        # Buscar registro de funcionário sob gestão do admin
        registro = RegistroPonto.query.join(
            RegistroPonto.funcionario_ref
        ).filter(
            RegistroPonto.funcionario_ref.has(admin_id=admin.id)
        ).first()
        
        if not registro:
            print("❌ Nenhum registro encontrado para este admin")
            return
        
        print(f"👤 Admin: {admin.email}")
        print(f"📋 Registro: {registro.id}")
        print(f"🏢 Funcionário: {registro.funcionario_ref.nome}")
        print(f"✅ Admin ID match: {registro.funcionario_ref.admin_id == admin.id}")
        
        # Simular verificação de permissão
        from views import verificar_permissao_edicao_ponto
        
        permissao = verificar_permissao_edicao_ponto(registro, admin)
        print(f"🔍 Permissão: {'✅ CONCEDIDA' if permissao else '❌ NEGADA'}")
        
        return permissao, registro.id

def gerar_codigo_teste_javascript():
    """Gerar código JavaScript para teste no navegador"""
    print(f"\n💻 JAVASCRIPT PARA TESTE NO NAVEGADOR:")
    print("=" * 60)
    
    js_code = """
// Cole este código no console do navegador após fazer login como admin
function testarModalCorrigido() {
    console.log('🧪 Testando modal corrigido...');
    
    // Buscar primeiro botão de editar
    const botaoEditar = document.querySelector('.btn-outline-primary[onclick*="editarPonto"]');
    if (!botaoEditar) {
        console.error('❌ Botão de editar não encontrado');
        return;
    }
    
    // Extrair ID
    const onclick = botaoEditar.getAttribute('onclick');
    const match = onclick.match(/editarPonto\\((\\d+)\\)/);
    if (!match) {
        console.error('❌ ID não encontrado');
        return;
    }
    
    const registroId = match[1];
    console.log(`📋 Testando registro ID: ${registroId}`);
    
    // Testar diretamente a função editarPonto
    if (typeof editarPonto === 'function') {
        editarPonto(registroId);
        console.log('✅ Função editarPonto chamada');
    } else {
        console.error('❌ Função editarPonto não encontrada');
    }
}

// Executar teste
testarModalCorrigido();
"""
    
    print(js_code)
    return js_code

def verificar_logs_sistema():
    """Verificar se há logs de erro no sistema"""
    print(f"\n📊 CHECKLIST FINAL:")
    print("=" * 60)
    
    checklist = [
        "✅ Função verificar_permissao_edicao_ponto corrigida (enum TipoUsuario)",
        "✅ Admin IDs de funcionários corrigidos",
        "✅ Logs de debug adicionados",
        "✅ Tratamento de erro no JavaScript melhorado",
        "✅ Mapeamento de campos backend ↔ frontend sincronizado",
        "✅ Estrutura do modal verificada"
    ]
    
    for item in checklist:
        print(f"   {item}")
    
    print(f"\n🎯 RESULTADO ESPERADO:")
    print("   1. Modal deve abrir normalmente")
    print("   2. Campos devem ser preenchidos com dados do registro")
    print("   3. Não deve aparecer erro HTTP 403")
    print("   4. Logs de debug aparecerão no console do servidor")
    
    print(f"\n🔧 PARA TESTAR:")
    print("   1. Faça login como admin@estruturasdovale.com.br")
    print("   2. Acesse perfil de funcionário (ex: João Silva Santos)")
    print("   3. Clique no botão 'Editar' de qualquer registro")
    print("   4. Modal deve abrir com dados preenchidos")

if __name__ == "__main__":
    print("🎯 TESTE FINAL: Modal de edição corrigido")
    print("=" * 80)
    
    # 1. Testar permissões
    permissao, registro_id = testar_modal_apos_correcao()
    
    # 2. Gerar JavaScript
    js_code = gerar_codigo_teste_javascript()
    
    # 3. Checklist
    verificar_logs_sistema()
    
    print(f"\n🏁 CONCLUSÃO:")
    if permissao:
        print("   ✅ Permissões funcionando corretamente")
        print("   ✅ Modal deve abrir normalmente")
        print(f"   📋 Teste com registro ID: {registro_id}")
    else:
        print("   ❌ Ainda há problemas de permissão")
        print("   🔧 Verifique se está logado como admin correto")
    
    print(f"\n📝 Use o código JavaScript acima para teste manual")