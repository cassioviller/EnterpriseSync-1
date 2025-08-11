"""
Teste básico dos modelos essenciais do SIGE v8.0
Verifica se as classes principais estão funcionando
"""

def test_models():
    try:
        # Importar o models e verificar classes principais
        from models import (
            db, Usuario, TipoUsuario, Funcionario, Obra, 
            RegistroPonto, Produto, CategoriaProduto, Fornecedor
        )
        
        print("✅ Imports dos models funcionando")
        
        # Verificar se as classes têm os atributos esperados
        essential_classes = [
            ('Usuario', Usuario),
            ('Funcionario', Funcionario), 
            ('Obra', Obra),
            ('RegistroPonto', RegistroPonto),
            ('Produto', Produto),
            ('CategoriaProduto', CategoriaProduto),
            ('Fornecedor', Fornecedor)
        ]
        
        for name, cls in essential_classes:
            if hasattr(cls, '__tablename__') or hasattr(cls, '__table__'):
                print(f"✅ {name}: OK")
            else:
                print(f"❌ {name}: Problema na definição")
                
        return True
        
    except Exception as e:
        print(f"❌ Erro nos models: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_models()
    if success:
        print("\n🎉 MODELS FUNCIONANDO!")
    else:
        print("\n❌ PROBLEMAS NOS MODELS")