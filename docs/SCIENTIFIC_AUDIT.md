# Auditoria científica e decisão de publicação

**Data:** 11/11/2026. **Objeto:** manuscrito VAL de Cleilson Elias de Sousa,
datado de 10/05/2026, 19 páginas, fornecido integralmente em PDF nesta tarefa.
**Software:** implementação nova de referência, versão 0.1.0.

## Parecer

VAL é implementável como um controlador de seleção de memória com limiares
por domínio. O pacote é publicável como software experimental que permite
comparar alocação seletiva, adaptação externa e políticas de recuperação.
Seu resultado científico defensável é uma hipótese arquitetural testável.
O manuscrito precisa de revisão antes de ser apresentado como demonstração
de superioridade geral, teoria validada de consciência ou modelo biológico
estabelecido de hiperfoco/autismo/savantismo.

A contribuição pode ser útil sem originalidade absoluta: a avaliação prioritária
é identificar quando a seleção melhora recuperação sob orçamento, quando perde
informação periférica e quanto do efeito já é obtido por cotas simples. Este
pacote não constitui revisão exaustiva de anterioridade de memória por domínio,
roteamento, mixtures-of-experts, atenção ou alocação adaptativa.

## O núcleo que se sustenta

Substituir um escalar por Λ=(λ_1,...,λ_K) cria graus de liberdade para escolher
limiares distintos por domínio. Com λ uniforme, a regra de admissão volta à
regra escalar. A observação implementável é uma mudança no conjunto de entradas
admitidas; o ganho de desempenho depende da distribuição de entradas, relevância
futura, qualidade do roteamento, orçamento e política de descarte.

Se o score bruto H do domínio k tem função de distribuição F_k e o limiar é θ_k,
então P(G=1|k)=1-F_k(θ_k). Portanto, diminuir λ reduz o limiar e aumenta ou mantém
a admissão. Não garante utilidade maior, densidade de grafo maior nem ganho de
raciocínio. Para scores uniformes em [0,1], θ_min=0,1 e θ_max=0,9, a razão de
admissão λ=0,05 versus λ=0,5 é 0,86/0,50=1,72; 3,8 não é uma constante universal.

## Problemas matemáticos identificados

| Local do manuscrito | Problema | Tratamento nesta implementação |
|---|---|---|
| Seção 3.1 / VAL-1 | Extremos λ=0/1 não implicam automaticamente passagem total/bloqueio total | Regra estrita preservada; teste dos extremos e escala explícita |
| VAL-2 | α, β e discretização não especificados; vetor de memória não define grafo | Impulsos e decaimento exato; taxas iguais por padrão e grafo separado |
| VAL-4 | ρ/λ singular em λ=0; f e relação com consciência não definidas | Nenhum C de consciência calculado |
| VAL-5 | 1,855 é substituição em um modelo com δ_max escolhido | Implementado como multiplicador, sem calibração biológica alegada |
| VAL-6 | Baseline sobe com o score; urgência não fica elevada por definição | EMA por domínio, com referência e consulta na mesma escala |
| VAL-7 | Gate usa H, sombra usa H_eff contra o mesmo limiar | Política literal e faixa de descarte expostas; alternativa identificada |
| VAL-8 | P(A e B)=P(A)P(B) requer independência; interseção não supera marginais | Evento conjunto observado, sem produto de probabilidades |
| VAL-9/10 | Descer gradiente de valor contradiz maximização do valor | Projeção de ascensão em V-K, gradiente fornecido pelo host |
| VAL-11 | Ranks contínuos/ilimitados e singulares em λ=0 | Piso de λ, teto inteiro e orçamento total; apenas plano |
| VAL-12 | Temperatura pequena não demonstra insight ou exploração sistemática | Plano com piso e status de geração não executada |
| Seção 10 | μ=0 gera λ_baseline/2; prior não define aprendizagem nem competição | Motivação autônoma permanece em aberto |

## Por que o Teorema VAL-1 não está demonstrado

O enunciado agrega quatro conclusões fortes que não decorrem da existência de
um componente pequeno de Λ: superioridade global, densidade local estritamente
maior, mais eventos cruzados e vantagem temporal monotônica. O esboço assume
justamente relações que precisaria demonstrar: mais memória implica maior
densidade; baselines permitem urgência sempre maior; distribuição alimenta os
domínios focados; conexões continuam aumentando sem limite. VAL-2 usa H bruto,
enquanto seu argumento invoca H_eff sem alterar formalmente aquela equação.

Um contraexemplo à superioridade global cabe em dois domínios. Considere
Λ=(0,05;0,95), média 0,5, θ_min=0,1, θ_max=0,9 e duas entradas colineares de
score 0,6, ambas no segundo domínio. O VAL rejeita as duas porque θ_2=0,86;
o escalar admite ambas porque θ=0,5. Com conexão por similaridade, a densidade
ativa do domínio é 0 no VAL e 1 no escalar. A soma ponderada ρ/λ é 0 versus 2.
Para f estritamente crescente e termo de sombra com coeficiente zero ou
suficientemente pequeno, a alegação C_VAL>C_escalar não se segue e pode inverter.
O termo de sombra não tem definição que restaure a desigualdade universal.

Mesmo num domínio alimentado continuamente, densidade normalizada pode cair:
duas memórias conectadas têm densidade 1; acrescentar uma memória sem arestas
reduz para 1/3. Contagem crescente não é densidade crescente. Com capacidade
finita e ρ_k∈[0,1], o proxy regularizado Σρ_k/max(λ_k,ε) tem teto K/ε. Isso
não proíbe ganhos locais; impede a inferência de divergência ilimitada desse proxy.

Outra falha é a linha de base da urgência: para h_q=bar(h)_k, Ω=0,5 para
qualquer λ. Baixa inibição não implica surpresa sustentada. E A∩B⊆A,B implica
P(A∩B)≤min(P(A),P(B)); dois eventos de ressonância não têm probabilidade maior
que cada marginal. Mudanças entre arquiteturas exigem distribuição conjunta.

Todos esses exemplos são executáveis em `val audit` e ficam registrados em
`validation/counterexamples.json`. Refutar a generalidade não elimina a
utilidade da hipótese de seleção por domínio; exige restringir seu enunciado.

## Previsões numéricas e arquivo de sombras

Os fatores 3,8x, razão sombras/ativos>10:1 e aumento de Eureka em ordens de
magnitude não vêm acompanhados de dados, código original ou condições suficientes
para reprodução no PDF. São previsões a especificar, não resultados certificados.

Há tensão entre "quase tudo consolida" e "sombras excedem ativos em 10:1" quando
ambos são conjuntos disjuntos sob o mesmo fluxo. No exemplo uniforme [0,1],
λ=0,05, δ_max=0,9 e θ_shadow_global=0,12, a faixa literal de sombras tem
probabilidade (0,14-0,006)/1,855≈0,07224; ativos têm probabilidade 0,86. A razão
é aproximadamente 0,084, abaixo de 0,1. Essa conta não prevê uma taxa biológica:
mostra que >10:1 não é consequência geral das equações. O cálculo não usa tetos
de retenção; estoques e fluxos também precisam ser distinguidos.

## Fundamento neurocientífico: alcance real das fontes

**Carson, Peterson e Higgins (2003): acesso ao resumo bibliográfico.** O trabalho
relaciona baixa inibição latente e realização criativa em amostras jovens de alto
QI. Isso oferece motivação para a hipótese; não identifica λ neural por domínio,
fórmula inversa de consciência ou demonstração de redução de risco clínico. A
associação não fornece a calibração numérica do VAL. DOI:
[10.1037/0022-3514.85.3.499](https://pubmed.ncbi.nlm.nih.gov/14498785/).

**Dwyer et al. (2024): texto integral acessível na editora.** Questionários em
492 adultos associaram hiperfoco e desatenção em grupos neurodivergentes e
descreveram experiências de hiperfoco com impactos favoráveis e desfavoráveis.
Esse desenho não mede um portão de consolidação λ_k nem identifica sua causa
neural. A inferência de equivalência formal entre perfil humano e vetor VAL
permanece uma analogia de modelagem. DOI:
[10.1177/27546330241237883](https://journals.sagepub.com/doi/full/10.1177/27546330241237883).

**Snyder (2009): texto integral no PMC.** O autor apresenta o acesso a informação
menos processada por desinibição como hipótese e discute evidências e induções
parciais. O texto não prova que toda capacidade existe pronta em qualquer rede,
nem fixa 1/λ como lei de resolução cognitiva. DOI:
[10.1098/rstb.2008.0290](https://pmc.ncbi.nlm.nih.gov/articles/PMC2677578/).

Nenhuma dessas fontes mede consciência do software ou valida os parâmetros
numéricos do manuscrito. Não se deve tratar autismo como um perfil único ou
inferir capacidades clínicas a partir de uma configuração artificial.

## Critério de publicação e próximos experimentos

**Publicável agora:** referência executável, API/CLI, decisões transparentes,
limites de recursos, testes, fontes e benchmark de recuperação sintética.
**Revisão necessária no texto:** substituir "prova"/"teorema" por conjectura
condicional ou proposição realmente demonstrada, remover equivalências clínicas
e separar previsões numéricas de observações executadas.

Uma proposição corrigida possível: sob o mesmo score, mesmo domínio e limiares
lineares crescentes em λ, reduzir λ não diminui a probabilidade de admissão.
Para concluir maior desempenho é preciso especificar como utilidade se relaciona
com score e domínio, a competição de recursos e o teste final. O custo de ignorar
domínios periféricos é parte do objetivo, não apenas um efeito colateral.

Os próximos testes devem, nesta ordem: usar corpus e consultas reais separados
em calibração e avaliação; comparar cotas e seleção por relevância sob mesmo
orçamento de bytes; medir abstenção, erros de roteamento e mudança de tarefa;
avaliar A3 aprendido sem sinais oraculares; integrar um modelo pequeno somente
depois de estabelecer ganho de recuperação; testar interferência após LoRA real.
O computador informado pelo autor é suficiente para o controlador e esses
testes iniciais de memória; o pacote atual executa em CPU e não requer GPU.

Nenhum novo experimento biológico ou de consciência foi realizado. Veja
`validation/validation.json` para verificações efetivamente executadas.
