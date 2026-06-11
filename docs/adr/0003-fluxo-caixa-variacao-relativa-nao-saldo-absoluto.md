# Fluxo de caixa mostra variação acumulada relativa, não saldo bancário absoluto

**Status:** accepted

A tela de Fluxo de Caixa não tem como exibir um saldo bancário absoluto confiável: não existe histórico de saldo e os saldos atuais dos bancos (`BancoEmpresa.saldo_atual`) não são mantidos na prática (ficam em 0). Decidimos que a linha de evolução do fluxo **parte de 0 e mostra a variação acumulada de caixa do período** (apenas movimentos **Realizados**), rotulada como tal — não como "saldo". O total real dos bancos aparece como KPI separado ("Saldo em banco"), assumindo o valor verdadeiro (hoje R$ 0) em vez de mascará-lo. **Realizado** e **Previsto** são apresentados separadamente em toda a tela (duas linhas no gráfico, colunas distintas na tabela), nunca somados num número único.

Consideramos reconstruir o saldo de abertura de cada período (`saldo_inicial` + `data_saldo_inicial` por banco + replay dos movimentos realizados até o início do período), mas é frágil enquanto os saldos bancários não forem mantidos e não agrega valor com os bancos zerados. Quando os saldos passarem a ser mantidos, dá para evoluir a linha para saldo absoluto sem mudar a estrutura da tela.
