# Product

## Register

product

## Users

**Administradores de construtoras e escritórios de engenharia** — donos, engenheiros responsáveis e gestores de obras que precisam orçar serviços, emitir propostas comerciais para clientes e acompanhar a execução financeira de obras. Não são designers nem devs. Usam o sistema diariamente para tomar decisões de custo, aprovar compras e cobrar clientes. Chegam ao sistema via desktop/laptop em escritório ou canteiro.

**Perfil técnico:** entendem planilhas Excel profundamente (é o benchmark de comparação constante), conhecem terminologia de construção civil (insumos, composições, BDI, empreiteiro, medição, RDO), mas não têm paciência para UX confuso. Se o sistema não for mais rápido que a planilha, voltam para a planilha.

## Product Purpose

SIGE é um sistema web de gestão para construtoras. Centraliza o ciclo completo de uma obra:

1. **Catálogo paramétrico** — insumos com preço histórico, coeficientes e fator comercial (embalagem)
2. **Orçamento interno** — composição de serviços por item, custo técnico × custo real de compra, margens
3. **Proposta comercial** — gerada a partir do orçamento, enviada ao cliente para aprovação
4. **Execução** — cronograma, RDO (Relatório Diário de Obra), medições, controle de progresso
5. **Financeiro** — custo orçado × custo real, comparativo com planilha do cliente

Sucesso é medido por: o gestor consegue montar um orçamento completo mais rápido do que no Excel e com menos erros de arredondamento ou preço desatualizado.

## Brand Personality

Funcional, confiável, direto. O sistema é uma ferramenta de trabalho séria — não é um produto de marketing. O tom é **técnico-objetivo** (usa os termos certos de construção civil), **eficiente** (cada tela faz o que precisa sem cerimonias), e **honesto** (não esconde complexidade, mas também não a amplifica).

Três palavras: **preciso, robusto, profissional**.

## Stack & Constraints

- **Backend:** Python / Flask, PostgreSQL, SQLAlchemy
- **Frontend:** Bootstrap 5 (bs5), Jinja2 templates, vanilla JS (sem framework)
- **Ícones:** Font Awesome 5/6
- **Inputs numéricos:** sempre formato pt-BR (vírgula decimal, ponto milhar) — R$ 1.234,56
- **Tema Bootstrap:** padrão com overrides; sem tema customizado complexo
- **Mobile:** responsivo mas uso primário é desktop

## Anti-references

Evitar:
- **Estética SaaS startup** — cards com gradiente, dark mode por padrão, glassmorphism
- **Dashboard de métricas vazio** — gráficos decorativos sem dado real
- **Jargão genérico de software** — "workspace", "kanban", "sprint" — usar terminologia de construção civil
- **Formulários infinitos em uma página** — quebrar em seções claras com hierarquia visual
- **Tabelas sem contexto** — sempre indicar o que cada coluna significa para quem chegou pela primeira vez

## Accessibility & Inclusion

- Foco visível em todos os inputs (crítico — usuários navegam por Tab em formulários longos)
- Contraste adequado em labels de status (verde/vermelho/amarelo devem ter fallback textual)
- Tooltips com `data-bs-toggle="tooltip"` para abreviaturas e campos técnicos
- Responsivo até 768px mas otimizado para 1280px+
