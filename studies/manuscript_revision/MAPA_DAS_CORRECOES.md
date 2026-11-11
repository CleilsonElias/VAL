# Reestruturação do artigo VAL

Data 11 de novembro de 2026

O artigo foi reescrito em inglês, preservando o nome VAL e o controle de inibição
por domínio. A contribuição agora é um mecanismo testável de seleção de memória
sob recursos limitados. O texto apresenta definições, proposições com provas,
contraexemplos, método experimental e resultados, com hipóteses cognitivas em
seu devido nível de evidência.

## Estrutura do manuscrito

| Seção | Função científica |
|---|---|
| 1 Introduction | Problema concreto e pergunta sobre vantagem frente a controles simples |
| 2 Background and relation to prior work | Motivação biológica limitada e relação com memória externa existente |
| 3 Controller specification | Entradas, roteamento, limiares, arquivo de sombras e recuperação definidos |
| 4 Properties and failure conditions | Duas proposições locais demonstradas e contraexemplos às inferências fortes |
| 5 Task value and adaptation | Objetivo, sinal correto de atualização e dependência de gradientes externos |
| 6 Reference implementation | O que o software realmente executa e qual configuração seleciona a revisão |
| 7 Experimental methods | Políticas, orçamentos, sinais de contexto, erros de rota e métricas |
| 8 Results | Dados executados, diferenças pareadas e resultados negativos |
| 9 Discussion | Limitações e experimento seguinte capaz de distinguir as alternativas |
| 10 Conclusion | Conclusão limitada aos mecanismos e testes apresentados |
| Appendix A | Correspondência entre elementos do original e sua posição corrigida |
| Appendix B | LoRA, REM e motivação como extensões ainda não validadas |
| Appendix C | Acesso às fontes e reprodução |

## Disparates corrigidos

O antigo teorema de superioridade geral foi substituído por monotonicidade da
admissão e ordenação de uma soma escalar descontada sob pesos fixos não negativos.
Nenhuma das proposições promete melhor recuperação, densidade crescente,
consciência ou criatividade. A norma de uma soma vetorial pode diminuir por
cancelamento; isso também foi explicitado.

A divisão por λ deixou de funcionar como suposta medida de consciência. Os
arquétipos com rótulos clínicos foram substituídos por políticas computacionais.
As fontes de neurociência sustentam a motivação da hipótese, sem serem usadas
para derivar parâmetros ou equivalências entre pessoas e configurações artificiais.

O portão e o arquivo de sombras usam o mesmo score na formulação revista. Isso
elimina a faixa em que uma observação era rejeitada pelo score bruto, mas também
recusada como sombra porque seu score amplificado ultrapassava o limiar superior.
A regra anterior continua apenas como controle experimental identificado.

A atualização de valor passou a ser ascensão de V menos custos, com projeção
em [0,1]. O texto explica que um portão indicador não fornece automaticamente
um gradiente útil e que os gradientes do estudo são fornecidos externamente.
A probabilidade conjunta de ressonância não é tratada como produto de marginais
sem independência, nem como evidência de insight criativo.

Os fatores 3,8x, razão de sombras acima de 10:1 e ganho de informação de 1,86x
deixaram de aparecer como resultados demonstrados. São quantidades dependentes
de parâmetros e distribuição ou, no último caso, uma substituição numérica no
multiplicador proposto. LoRA e REM estão em apêndice com status de planejamento.

## Comparação experimental adicional

Foram executadas 864 simulações novas com 16 sementes, 9 políticas, 3 cenários e
2 níveis de erro de roteamento. Cada execução utiliza 320 episódios e 96 consultas.
Todas as políticas têm teto total de 128 episódios. Os comparadores adaptativos
recebem o mesmo sinal externo de mudança de tarefa. Não houve treinamento de
motivação, descoberta autônoma de tarefa ou experimento biológico.

Sem erro de rota, o VAL seletivo com sombras corrigidas atingiu 73,83% no cenário
focado, contra 39,91% do limiar uniforme e 99,09% de cotas simples. Após a troca,
o VAL adaptativo atingiu 96,68% e as cotas adaptativas 100%. Com 20% de erro de
rota na troca, a ordem local se inverteu: VAL adaptativo 88,28% e cotas 85,09%.
Essa dependência das condições impede uma conclusão de dominância geral.

A amplificação não alterou Recall@1 em nenhuma semente e condição deste protocolo
com sombras consistentes. A ablação preservou a retenção e variou a escala da
urgência. Esse resultado não prova ausência de efeito em outros scores de consulta
ou limiares; impede atribuir a ela um ganho não observado no estudo executado.

Os seis novos testes focados passaram. Um deles garante que, entre os níveis de
erro, apenas o roteamento mude: fatos, vetores, scores e consultas são preservados.
O núcleo original é uma cópia sem
alterações da versão 0.1.0 que já havia passado por 41 testes. O novo estudo
utiliza explicitamente shadow_policy="raw_interval"; o padrão do pacote 0.1.0
continua sendo a política anterior. O artigo não afirma que uma nova versão
de software foi publicada.

## O que ainda falta para uma submissão forte

O manuscrito agora pode ser avaliado como formulação metodológica com estudo
sintético. Uma contribuição empírica mais forte requer corpus real, encoder
fixo, consultas de avaliação separadas da calibração e comparação sob o mesmo
orçamento de bytes e latência. Os sinais de contexto precisam ser fornecidos
igualmente ou aprendidos por todos os controles adaptativos. O ganho deve
sobreviver a cotas, FIFO e seleção por relevância.

O suplemento preserva código, logs, dados por semente, figuras, fontes editáveis
e hashes. O artigo de origem e o pacote entregue anteriormente permanecem como
registros da formulação anterior; esta entrega é uma nova versão do manuscrito.
