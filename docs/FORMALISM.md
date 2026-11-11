# Do manuscrito à implementação

Fonte histórica: manuscrito VAL fornecido pelo autor, 19 páginas, datado de
10/05/2026. As referências VAL-N identificam sua numeração original. A versão
0.2.0 acompanha o artigo revisado de 11/11/2026 e usa a regra coerente abaixo.

## Entrada e seleção

O domínio dominante é `argmax p_k`, com empate resolvido pelo menor índice.
Embeddings são normalizados; afinidades de roteamento são não negativas e
normalizadas pela soma. Esses vetores não vêm de atenção de um transformer.
O host pode fornecer score h em [0,1], calculado em representação independente.
Sem score explícito, a convenção compatível com o LLI-CAMS é:

\[
H_R=-\sum_{i\ne j}p_i p_j\log_2(p_i p_j)
   =-2\sum_i p_i(1-p_i)\log_2p_i,\qquad
h=H_R/(2\log_2 K).
\]

Para K=1 define-se h=0. Não é uma entropia de Shannon sobre pares distintos
normalizados: a massa fora da diagonal é `1-sum(p_i²)`. Para K=4 uniforme,
h=0,75. Roteamento quase unívoco produz h baixo; esse efeito pode contrariar a
retenção de fatos específicos úteis. Fornecer outro score exige validação do host.

\[
\theta_k=\theta_{min}+(\theta_{max}-\theta_{min})\lambda_k,\qquad
G(x,k)=\mathbf 1\{h(x)>\theta_k\}.
\]

O código preserva a desigualdade estrita de VAL-1. Não impõe artificialmente
"aceitar tudo em λ=0" nem "rejeitar tudo em λ=1": essas frases do manuscrito
dependem da escala do score e dos limiares. λ uniforme recupera a seleção
escalar, mas referências históricas por domínio continuam distintas de uma
única referência global do LLI-CAMS.

## Dinâmica de memória

VAL-2 não fixa α(λ), β(λ), escala temporal nem significado vetorial de x.
Nesta implementação os vetores x têm norma 1 e os eventos são impulsos:

\[
M_{k,n}=e^{-\beta_k\Delta t}M_{k,n-1}
       +\alpha_k G(x_n,k)h(x_n)\widehat x_n.
\]

O impulso independe de Δt: Δt=0 significa eventos simultâneos, não cancelamento
da consolidação. Não é a solução com fonte constante durante todo o intervalo.
α e β são iguais entre domínios por padrão, para não inserir um segundo efeito
de λ sem ablação. A opção `couple_rates=True` é uma hipótese de engenharia:
α_k=α_base(2-λ_k), β_k=β_base(0,1+0,9λ_k). Os benchmarks usam essa opção desligada.

M é uma soma vetorial com esquecimento, separada dos episódios recuperáveis.
Uma memória evictada pode continuar contribuindo para M até decair; M não
reconstrói seu texto e não é usado para simular recuperação factual.

## Amplificação e urgência

VAL-5/5.1 é implementada literalmente:

\[
h_{eff,k}=h[1+(1-\lambda_k)\delta_{max}].
\]

h_eff pode superar 1. Trata-se de score multiplicado por um parâmetro; não
é demonstração de aumento da informação contida no vetor. δ_max=0,9 é uma
escolha do manuscrito, sem calibração fornecida. 1,855 resulta da substituição
λ=0,05, não de uma constante neurofisiológica deduzida.

A referência EMA bruta é atualizada só após a decisão, com observações do
domínio dominante, inclusive rejeitadas:

\[
\bar h_{k,n}=(1-\gamma)\bar h_{k,n-1}+\gamma h_n,\quad
\Omega(q,k)=\sigma\{a_\Omega [1+(1-\lambda_k)\delta_{max}](h_q-\bar h_k)\}.
\]

Escalar a referência com o λ atual mantém a unidade do score coerente durante
adaptação. Para λ fixo equivale a suavizar h_eff, com prior igualmente escalado.
Na média calibrada Ω=0,5 independentemente de λ. Não se presume urgência
permanentemente maior sob baixa inibição. `baseline_rate` é γ, fixo e explícito.

## Sombras e recuperação

Por padrão, observações rejeitadas usam o mesmo score bruto do portão ativo:

\[
\theta_{shadow,global}\lambda_k<h\le\theta_k.
\]

`shadow_policy="raw_interval"` é a regra do artigo revisado e o novo padrão.
A política explícita `paper` preserva VAL-7: θ_shadow<h_eff<θ_k. A mistura
de escalas nessa regra antiga pode deixar uma faixa sem destino: h≤θ_k,
mas h_eff≥θ_k. Sombras e ativos são disjuntos. Igualdades nos limiares seguem
exatamente cada política. Os pools aplicam FIFO separadamente;
ativos evictados não são automaticamente reciclados como sombras.

Consulta recupera ativos com cosseno positivo e sombras cujo
`cos(q,s)*Omega(q,domain_s)>resonance_threshold`. O score de ordenação final é o
cosseno, com desempate por ID. Texto de evidência é retido nas sombras: este
pacote não simula recuperação exata de conteúdo textual apagado. O roteamento
da consulta fornece o score de fallback; a busca considera todos os domínios.

`cross_resonance_pairs` registra pares de domínios primários com sombras que
passaram pela condição na mesma consulta. Não multiplica probabilidades marginais:
as ativações compartilham consulta e arquivo, portanto a independência não é dada.
Consultas não alteram médias, pesos, categorias, grafo nem estado persistido.

## Grafo, ranks e REM

Os ativos formam um grafo não direcionado por similaridade, com limiar e grau
máximo em ambos os extremos. Densidade intradomínio é E/[N(N-1)/2], ou zero para
N<2. Um nó pode ter domínios secundários quando sua afinidade supera o limiar de
membro; isso não significa que passou pelo portão de cada domínio. Aresta entre
primários distintos é contada como cruzada. Similaridade não demonstra causalidade.

O código não calcula C(S,t) de VAL-4. f, a topologia de S e sua relação com
consciência não são operacionalizados no manuscrito. A auditoria usa um score
de densidade explicitamente rotulado para construir contraexemplos, sem chamá-lo
de medida de consciência. Contagem de nós, densidade e massa são objetos distintos.

O plano de ranks regulariza VAL-11:

\[
r_k^*=\min(r_{cap},\lceil r_{base}/\max(\lambda_k,\varepsilon)\rceil),\qquad
\sum_k r_k\le B.
\]

Se necessário, distribui-se B proporcionalmente aos alvos e arredonda-se por
maiores restos, com desempate pelo índice. Alguns ranks podem ser zero. Antes
de usar o plano num modelo real, o host precisa impor `rank_cap<=min(d_in,d_out)`
para cada camada e contabilizar parâmetros: soma de ranks não é VRAM.

O REM recebe `max(tau_min,tau_base*(lambda_k+lambda_j)/2)`; o piso evita
temperatura zero em um gerador que a exija positiva. O plano não executa geração,
treino, LoRA, replay, promoção ou avaliação da utilidade de uma ponte.

## Adaptação A3

Para maximizar utilidade líquida J=V-K, usa-se:

\[
\Lambda_{n+1}=\Pi_{[0,1]^K}\{\Lambda_n+\eta(\nabla V-\nabla K)\}.
\]

É descida na perda L=-V+K. VAL-9 do manuscrito contém -η∇V, que desce o valor
se V for uma recompensa. A correção é explícita. Não há gradiente clássico útil
através de um portão indicador; o host deve fornecer uma estimativa diferenciável,
diferenças finitas, otimização sem gradientes ou um objetivo substituto validado.
O código valida e aplica gradientes externos; não aprende a motivação intrínseca.
A fórmula de prior proposta na seção 10 retorna λ_baseline/2 com μ=0, por causa
de sigmoid(0)=0,5, e não contém por si um mecanismo competitivo entre domínios.

## Estado e custo

Persistência usa JSON versionado e transação SQLite com revisão esperada;
um escritor com revisão antiga recebe `RevisionConflict`. A CLI lê todas as
linhas e valida o novo estado antes de criar o banco. Consulta e plano são somente
leitura. Nenhuma serialização executável é carregada.

O núcleo é de um único thread; o host deve sincronizar acessos concorrentes em
memória e repetir sua própria operação após conflito, com estado atualizado.
Apenas IDs ainda retidos são deduplicados. Não existe ledger histórico ilimitado;
unicidade global é responsabilidade do host. Um snapshot guarda configuração,
baselines, contadores, massa, vetores e texto dos episódios retidos. Snapshot
externo com estrutura incompatível é rejeitado; não há migração automática.

Com A ativos, S sombras, D dimensões e K domínios, observação custa O(KD+A+S),
consulta O((A+S)D) e reconstrução do grafo O(A²D+A²log A). Memória retida é
O((A+S+K)D+texto). Há tetos de itens, não de bytes por texto. Não há HNSW,
ACS dual Alpha/Omega, processo de transformer ou interface web nesta versão.
