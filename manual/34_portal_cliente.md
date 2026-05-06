# Portal do Cliente

O **Portal do Cliente** (`/portal/obra/<token>`) dá acesso **público** (sem login) ao cliente final de uma obra para acompanhar **progresso**, **cronograma**, **mapas de concorrência**, **pedidos de compra** e **enviar comprovantes de pagamento**. O acesso é controlado por um **token único** por obra.

## Para que serve

- Mostrar ao cliente o **andamento da obra** (RDOs, fotos, sub-atividades, ocorrências).
- Exibir o **cronograma do cliente** (versão simplificada, sem detalhes internos).
- Permitir que o cliente **aprove/recuse pedidos de compra** (mapas de concorrência V2).
- Receber **comprovantes de pagamento** com upload de arquivo.
- Apresentar a obra com **branding do tenant** (logo, cores, nome da empresa).

## Como acessar

- O administrador gera o **token** ao **ativar o portal** na ficha da obra (`/obras/detalhes/<id>` → seção "Portal do Cliente").
- O link enviado ao cliente tem o formato `https://<dominio>/portal/obra/<token>`.
- **Não exige login** — qualquer pessoa com o link entra. Ações destrutivas exigem que o portal esteja **ativo**.
- Sub-rotas: `/portal/obra/<token>/aprovar-compra`, `/portal/obra/<token>/comprovante`, etc. (todas validam o token).

## Fluxos principais

### 1. Ativar o portal e gerar o token

1. **Obras → Detalhes da obra → "Portal do Cliente"**.
2. Marque a opção **"Ativar Portal"** e clique em **"Salvar"**.
3. O sistema preenche `obra.token_cliente` com um valor aleatório (`secrets.token_urlsafe(32)`) e exibe o link para copiar.
4. **Atenção:** no demo Alfa há obras com `portal_ativo=True` mas `token_cliente=NULL` — confira se a ativação realmente gerou o token antes de enviar o link ao cliente.

### 2. Enviar o link ao cliente

1. Copie o link `https://<dominio>/portal/obra/<token>`.
2. Envie por e-mail ou WhatsApp; o cliente abre direto, sem cadastro.
3. A primeira visualização registra `obra.ultima_visualizacao_cliente = now()`.

### 3. Cliente acompanha a obra

1. O cliente abre o link → vê a tela `templates/portal/portal_obra.html` com:
   - **Cabeçalho** com logo do tenant.
   - **Resumo da obra** (nome, endereço, prazo, % concluído).
   - **Cronograma do cliente** (`CronogramaCliente` — visão simplificada).
   - **Galeria de fotos** dos RDOs.
   - **Lista de RDOs** com sub-atividades, mão-de-obra e ocorrências.
2. Se o admin desativar o portal (`portal_ativo=False`), o cliente passa a ver `templates/portal/portal_inativo.html` com o mesmo branding.

### 4. Aprovar/recusar pedido de compra

1. Quando há **mapa de concorrência V2** liberado para o cliente, aparece a seção **"Pedidos de Compra"**.
2. O cliente compara as cotações dos fornecedores e clica em **"Aprovar"** no preferido.
3. O POST autentica via token e grava a aprovação no `MapaConcorrenciaV2`.

### 5. Enviar comprovante de pagamento

1. O cliente clica em **"Enviar Comprovante"** dentro de um pedido aprovado.
2. Faz upload de arquivo — extensões permitidas: `.png`, `.jpg`, `.jpeg`, `.webp`, `.pdf` (até **5 MB**).
3. O arquivo é gravado com nome seguro (prefixo `comprovante_<id>_<hex>`) no diretório de comprovantes.
4. O lançamento financeiro fica disponível para conferência do tenant.

## Estrutura de templates

O template principal `portal_obra.html` é um shell que inclui parciais:

| Arquivo | Conteúdo |
|---------|----------|
| `templates/portal/_portal_styles.html` | Todos os estilos CSS do portal |
| `templates/portal/_portal_hero.html` | Card de progresso + KPIs |
| `templates/portal/_portal_cronograma.html` | Cronograma em árvore colapsável |
| `templates/portal/_portal_compras.html` | Compras pendentes + resolvidas + upload de comprovante |
| `templates/portal/_portal_medicoes.html` | Lista de medições |
| `templates/portal/_portal_mapas_v2.html` | Mapas de concorrência V2 (abertos e concluídos) |
| `templates/portal/_portal_rdos.html` | Lista de RDOs finalizados |
| `templates/portal/_portal_scripts.html` | JavaScript do mapa V2 (seleção interativa) |

Para mudanças visuais, edite a parcial correspondente ao trecho desejado — não é mais necessário navegar por 1300 linhas.

## Configuração de upload (ambiente)

| Variável | Significado | Padrão |
|----------|-------------|--------|
| `UPLOADS_PATH` | Diretório **base** para uploads persistentes (usado em produção/EasyPanel). O sistema cria `<UPLOADS_PATH>/comprovantes/` automaticamente. | `static/uploads/` (dentro do projeto) |
| `MAX_CONTENT_LENGTH` | Limite de payload HTTP (5 MB). Configurado em `app.py`. | `5242880` (5 MB) |

Em **desenvolvimento** (sem `UPLOADS_PATH`), os comprovantes ficam em `static/uploads/comprovantes/` e são servidos pelo Flask normalmente.  
Em **produção**, defina `UPLOADS_PATH=/var/data/uploads` (ou o caminho do volume persistente); os arquivos serão acessíveis via `/persistent-uploads/comprovantes/<nome>`.

## Dicas e cuidados

- **Token NULL com portal ativo** é uma falha de configuração — sem token, a URL não pode ser montada e o cliente não acessa. Reabra a tela da obra, desative e reative o portal para forçar a geração.
- Compartilhar o **token** equivale a compartilhar o portal — qualquer pessoa com o link entra. Para revogar acesso, **desative o portal** ou **regenere o token**.
- A separação entre `_get_obra_by_token` (usado em ações POST) e `_resolve_obra_for_view` (usado em GET) é proposital: ações destrutivas só rodam com portal ativo; visualizações permitem mostrar a tela amigável de "portal desativado".
- Upload de comprovante: arquivos > 5 MB ou com extensão não permitida são rejeitados com mensagem amigável — sem exposição de stack trace ao cliente.
- O portal **não** é multi-tenant no sentido de login: o token já carrega a obra (e o tenant). Não exponha o token em URLs públicas (Trello, redes sociais).
