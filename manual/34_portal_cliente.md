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
3. O sistema deveria preencher `obra.token_cliente` com um valor aleatório (`secrets.token_urlsafe(32)`) e exibir o link para copiar.
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
2. Faz upload de arquivo (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.pdf`) — limites de extensão definidos em `ALLOWED_EXTENSIONS`.
3. O arquivo é gravado em `static/uploads/comprovantes/` com nome seguro.
4. O lançamento financeiro fica disponível para conferência do tenant.

## Dicas e cuidados

- **Token NULL com portal ativo** é uma falha de configuração — sem token, a URL não pode ser montada e o cliente não acessa. Reabra a tela da obra, desative e reative o portal para forçar a geração.
- Compartilhar o **token** equivale a compartilhar o portal — qualquer pessoa com o link entra. Para revogar acesso, **desative o portal** ou **regenere o token**.
- A separação entre `_get_obra_by_token` (usado em ações POST) e `_resolve_obra_for_view` (usado em GET) é proposital: ações destrutivas só rodam com portal ativo; visualizações permitem mostrar a tela amigável de "portal desativado".
- Os uploads vão para `static/uploads/comprovantes/` — mantenha backup desse diretório no plano de cópia/restore.
- O portal **não** é multi-tenant no sentido de login: o token já carrega a obra (e o tenant). Não exponha o token em URLs públicas (Trello, redes sociais).
- O template `portal_obra.html` é **grande (~1300 linhas)** — para mudanças visuais, edite com cuidado e teste em pelo menos uma obra com poucos e uma com muitos RDOs.
