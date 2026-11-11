# Resultados revisados e registro histórico

O resultado científico principal desta publicação é o estudo de **864 execuções**
em [studies/manuscript_revision/](../studies/manuscript_revision/README.md),
com dados pareados entre níveis de erro, nove políticas e controles adaptativos
com o mesmo contexto externo. Veja o artigo revisado e CROSS_PROJECT_IMPACT.md.

O registro abaixo é o estudo exploratório 0.1.0, preservado para transparência.
Seu benchmark usa a política `paper` explicitamente. O gerador antigo consome
o RNG de forma diferente entre níveis de erro; portanto, não se pode atribuir
suas diferenças entre 0% e 20% apenas ao roteamento. Não fundamenta os novos
percentuais nem representa a regra padrão de VAL 0.2.0.

## Registro histórico 0.1.0

Data: 11/11/2026. Fonte: `validation/benchmark.json`.

## Protocolo

8 sementes × 3 cenários × 2 níveis de erro de roteamento × 7 políticas = **336 execuções**.
Cada execução recebe 320 episódios de 12 dimensões e 48 consultas com códigos aleatórios.
Scores de seleção são sintéticos, independentes dos rótulos de relevância. Não houve ajuste de pesos.

Ativos e sombras têm tetos de 64 episódios cada. O FIFO por cotas usa o mesmo teto total de 128 como ativos:
[96, 13, 10, 9] slots por domínio. A ablação sem sombras tem somente 64 slots.
A1 usa [0,05; 0,90; 0,90; 0,90]; o escalar usa λ=0,6875. A2 usa 0,20 em todos os domínios.
A3 começa como A1 e recebe o domínio-alvo na metade do cenário de troca. É contexto externo, não motivação aprendida.

## Roteamento com 0% de erro

Recall@1 médio entre sementes; valores em porcentagem.

| Política | Focado | Troca de tarefa | Difuso |
|---|---:|---:|---:|
| Escalar (média de A1) | 42,71% | 61,20% | 39,32% |
| A1 fixo | 67,97% | 57,81% | 38,28% |
| A2 amplo | 33,59% | 56,77% | 32,29% |
| A3 com contexto externo | 67,97% | 92,45% | 38,28% |
| FIFO por cotas totais | 100,00% | 35,42% | 36,20% |
| A1 sem amplificação | 71,09% | 56,51% | 38,54% |
| A1 sem sombras | 67,45% | 4,95% | 18,23% |

## Roteamento com 20% de erro

Recall@1 médio entre sementes; valores em porcentagem.

| Política | Focado | Troca de tarefa | Difuso |
|---|---:|---:|---:|
| Escalar (média de A1) | 34,38% | 63,02% | 43,49% |
| A1 fixo | 62,50% | 57,29% | 41,67% |
| A2 amplo | 32,29% | 54,43% | 34,64% |
| A3 com contexto externo | 62,50% | 89,32% | 41,67% |
| FIFO por cotas totais | 76,30% | 37,50% | 39,58% |
| A1 sem amplificação | 63,02% | 57,81% | 42,19% |
| A1 sem sombras | 56,25% | 8,85% | 23,18% |

## Interpretação

A1 supera o escalar no cenário focado, mas o FIFO simples por cotas totais supera A1 nesse mesmo cenário.
Assim, a utilidade da alocação especializada aparece no teste; uma vantagem específica do formalismo VAL sobre alocação simples ainda não aparece.
A1 perde para o escalar após a mudança de tarefa. A3 melhora quando o alvo é fornecido externamente.
Na consulta difusa, diferenças pequenas não apoiam uma conclusão universal.

## Variabilidade pareada e uso de memória

Intervalos normais descritivos de 95% para a diferença de Recall@1 contra o escalar, por semente.
Não representam intervalos calibrados para uma população de tarefas. Não houve correção para comparações múltiplas.

| Cenário, sem erro de rota | Política | Diferença (p.p.) | Intervalo (p.p.) | Ativos + sombras médios | Payload médio (bytes) |
|---|---|---:|---:|---:|---:|
| Focado | A1 fixo | 25.26 | [17.41, 33.11] | 64.00 + 64.00 | 57519 |
| Focado | A3 com contexto externo | 25.26 | [17.41, 33.11] | 64.00 + 64.00 | 57519 |
| Focado | FIFO por cotas totais | 57.29 | [46.71, 67.87] | 114.50 + 0.00 | 51471 |
| Troca de tarefa | A1 fixo | -3.39 | [-10.90, 4.13] | 64.00 + 64.00 | 57519 |
| Troca de tarefa | A3 com contexto externo | 31.25 | [24.18, 38.32] | 64.00 + 64.00 | 57498 |
| Troca de tarefa | FIFO por cotas totais | -25.78 | [-35.57, -15.99] | 114.50 + 0.00 | 51471 |
| Difuso | A1 fixo | -1.04 | [-6.10, 4.02] | 64.00 + 64.00 | 57519 |
| Difuso | A3 com contexto externo | -1.04 | [-6.10, 4.02] | 64.00 + 64.00 | 57519 |
| Difuso | FIFO por cotas totais | -3.12 | [-9.15, 2.90] | 114.50 + 0.00 | 51471 |

`payload_bytes` mede a serialização JSON dos episódios retidos, não tamanho de arquivo SQLite ou RAM real.
Os tetos são iguais em episódios totais, mas ocupação, bytes e admissão realizados diferem e são reportados.
As diferenças entre A1 e sua ablação sem amplificação também mudam a faixa literal de arquivamento de sombras.
Portanto, essa ablação mede um efeito composto sobre urgência e elegibilidade de sombras, não aumento isolado de informação.
A retirada das sombras reduz também o orçamento total; sua diferença não isola apenas o método de recuperação.

## Limites

Vetores aleatórios permitem recuperar episódios cuja direção foi preservada; não medem compreensão, verdade ou geração de linguagem.
Erros de roteamento da ingestão são simulados; consultas recebem o domínio verdadeiro. Não há encoder treinado ou avaliação de texto real.
O foco conhecido favorece tanto A1 quanto o FIFO especializado. Essa informação a priori é parte explícita do protocolo.
A avaliação não esgota controladores possíveis nem substitui um benchmark externo. Não houve treino LoRA, geração REM ou validação de consciência.

## Reprodução

```bash
python tools/validate.py --full-benchmark
```

Validação local: **41 testes aprovados** em Python 3.12.14.
O workflow GitHub foi configurado, mas não foi executado remotamente nesta entrega.
