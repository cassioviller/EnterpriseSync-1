# Prompt: Manual de Configuração Inicial - EnterpriseSync

## 🎯 Objetivo

Criar o **Capítulo 1** do manual de uso do sistema EnterpriseSync, focado na **Configuração Inicial e Instalação**.

## 📝 Estrutura do Manual

O manual deve ser escrito em **Markdown**, com linguagem clara, objetiva e profissional. Use tabelas, listas numeradas e imagens (placeholders) para facilitar o entendimento.

### **Capítulo 1: Configuração Inicial e Instalação**

#### **1.1. Introdução**
- Breve introdução ao EnterpriseSync e seus objetivos.
- Visão geral do que será coberto neste capítulo.

#### **1.2. Requisitos do Sistema**
- Tabela com requisitos de hardware e software (servidor, banco de dados, etc.).
- Requisitos para o cliente (navegador, sistema operacional).

#### **1.3. Instalação do Sistema**
- Passo a passo detalhado da instalação em um ambiente de produção (Docker/EasyPanel).
- Como clonar o repositório.
- Como configurar as variáveis de ambiente (`.env`).
- Como executar as migrações do banco de dados (`flask db upgrade`).
- Como iniciar o servidor.

#### **1.4. Primeiro Acesso e Configuração da Empresa**
- Como acessar o sistema pela primeira vez.
- Como criar o primeiro usuário **Super Admin**.
- Como preencher os dados da empresa (nome, CNPJ, endereço).
- Como configurar o logo da empresa.

#### **1.5. Configurações Globais**
- **1.5.1. Departamentos**
  - Como criar, editar e excluir departamentos.
  - Importância dos departamentos para organização.
- **1.5.2. Funções**
  - Como criar, editar e excluir funções/cargos.
  - Como vincular funções a departamentos.
- **1.5.3. Horários de Trabalho**
  - Como criar, editar e excluir horários de trabalho.
  - Como definir jornadas (segunda a sexta, sábado, etc.).
  - Como configurar tolerâncias de atraso.

#### **1.6. Gestão de Usuários**
- **1.6.1. Tipos de Usuário**
  - Tabela explicando os 4 tipos de usuário:
    - Super Admin
    - Admin
    - Gerente
    - Funcionário
- **1.6.2. Criando Usuários**
  - Passo a passo para criar um novo usuário.
  - Como vincular um usuário a um funcionário.
  - Como definir o tipo de usuário.
- **1.6.3. Editando e Desativando Usuários**
  - Como editar permissões.
  - Como desativar um usuário.

#### **1.7. Checklist de Configuração Inicial**
- Tabela com um checklist de todas as etapas de configuração inicial.
- Exemplo:

| Passo | Descrição | Status |
|:---|:---|:---:|
| 1 | Instalar o sistema | [ ] |
| 2 | Criar usuário Super Admin | [ ] |
| 3 | Configurar dados da empresa | [ ] |
| 4 | Criar departamentos | [ ] |
| 5 | Criar funções | [ ] |
| 6 | Criar horários de trabalho | [ ] |
| 7 | Criar usuários adicionais | [ ] |

## 🎨 Estilo e Tom

- **Tom**: Profissional, didático e acessível.
- **Linguagem**: Evitar jargões técnicos sempre que possível.
- **Formato**: Markdown, com uso de títulos, subtítulos, negrito, tabelas e listas.
- **Imagens**: Usar placeholders como `[IMAGEM: Tela de login]` ou `[IMAGEM: Formulário de criação de departamento]` para indicar onde as imagens devem ser inseridas.

## 🚀 Ação

Com base neste prompt, gere o arquivo `01_manual_configuracao_inicial.md` com o conteúdo completo do Capítulo 1.
