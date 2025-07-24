# Atualização do Card de Funcionário - v8.0.7

## Alterações Implementadas

### Modificações no Template `templates/funcionarios.html`

1. **Email substituído por Telefone**
   - Campo `kpi.funcionario.email` → `kpi.funcionario.telefone`
   - Agora mostra o número de telefone abaixo do nome do funcionário

2. **Departamento removido das informações**
   - Removida linha com ícone `fa-sitemap` e departamento
   - Mantidas apenas função e horário de trabalho
   - Layout mais limpo e focado

3. **Atributo de filtro atualizado**
   - `data-departamento` → `data-telefone` para filtros de busca

### Resultado Visual

**Antes:**
- Nome do funcionário
- Email
- Departamento (ícone departamento)
- Função (ícone função) 
- Horário (ícone relógio)

**Depois:**
- Nome do funcionário
- Telefone
- Função (ícone função)
- Horário (ícone relógio)

### Benefícios

- Interface mais limpa e menos poluída
- Informação de contato mais útil (telefone vs email)
- Foco nas informações mais relevantes para operação
- Mantém dados essenciais (função e horário)

### Data da Implementação
24 de julho de 2025

### Sistema
SIGE v8.0 - Sistema Integrado de Gestão Empresarial