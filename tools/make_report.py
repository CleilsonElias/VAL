"""Optional reporting tool: requires reportlab and matplotlib, not core dependencies.

Generates the PDF audit, a static figure, and docs/RESULTS.md from executed logs.
Run after `python tools/validate.py --full-benchmark`.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, findfont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak,
                               PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT/"validation/benchmark.json").read_text())
AUDIT = json.loads((ROOT/"validation/counterexamples.json").read_text())
VALIDATION = json.loads((ROOT/"validation/validation.json").read_text())
PROVENANCE = json.loads((ROOT/"validation/source_provenance.json").read_text())
SUMMARY = {(x["scenario"], x["routing_error"], x["policy"]): x for x in DATA["summaries"]}
NAMES = {"scalar_mean":"Escalar (média de A1)", "A1_fixed":"A1 fixo", "A2_broad":"A2 amplo",
         "A3_context":"A3 com contexto externo", "quota_fifo":"FIFO por cotas totais",
         "A1_no_amplification":"A1 sem amplificação", "A1_no_shadows":"A1 sem sombras"}
SCENARIOS = {"focused":"Focado", "shifted":"Troca de tarefa", "diffuse":"Difuso"}


def percent(value):
    return f"{100*value:.2f}%".replace(".", ",")


def build_results():
    lines = ["# Resultados executados", "", "Data: 11/11/2026. Fonte: `validation/benchmark.json`.", "",
             "## Protocolo", "", "8 sementes × 3 cenários × 2 níveis de erro de roteamento × 7 políticas = **336 execuções**.",
             "Cada execução recebe 320 episódios de 12 dimensões e 48 consultas com códigos aleatórios.",
             "Scores de seleção são sintéticos, independentes dos rótulos de relevância. Não houve ajuste de pesos.", "",
             "Ativos e sombras têm tetos de 64 episódios cada. O FIFO por cotas usa o mesmo teto total de 128 como ativos:",
             "[96, 13, 10, 9] slots por domínio. A ablação sem sombras tem somente 64 slots.",
             "A1 usa [0,05; 0,90; 0,90; 0,90]; o escalar usa λ=0,6875. A2 usa 0,20 em todos os domínios.",
             "A3 começa como A1 e recebe o domínio-alvo na metade do cenário de troca. É contexto externo, não motivação aprendida.", ""]
    for error in (0.0, 0.2):
        lines.extend([f"## Roteamento com {int(error*100)}% de erro", "",
                      "Recall@1 médio entre sementes; valores em porcentagem.", "",
                      "| Política | Focado | Troca de tarefa | Difuso |", "|---|---:|---:|---:|"])
        for policy in NAMES:
            values = [percent(SUMMARY[(scenario, error, policy)]["recall_mean"])
                      for scenario in SCENARIOS]
            lines.append("| "+NAMES[policy]+" | "+" | ".join(values)+" |")
        lines.append("")
    lines.extend(["## Interpretação", "",
        "A1 supera o escalar no cenário focado, mas o FIFO simples por cotas totais supera A1 nesse mesmo cenário.",
        "Assim, a utilidade da alocação especializada aparece no teste; uma vantagem específica do formalismo VAL sobre alocação simples ainda não aparece.",
        "A1 perde para o escalar após a mudança de tarefa. A3 melhora quando o alvo é fornecido externamente.",
        "Na consulta difusa, diferenças pequenas não apoiam uma conclusão universal.", "",
        "## Variabilidade pareada e uso de memória", "",
        "Intervalos normais descritivos de 95% para a diferença de Recall@1 contra o escalar, por semente.",
        "Não representam intervalos calibrados para uma população de tarefas. Não houve correção para comparações múltiplas.", "",
        "| Cenário, sem erro de rota | Política | Diferença (p.p.) | Intervalo (p.p.) | Ativos + sombras médios | Payload médio (bytes) |",
        "|---|---|---:|---:|---:|---:|"])
    for scenario in SCENARIOS:
        for policy in ("A1_fixed", "A3_context", "quota_fifo"):
            row = SUMMARY[(scenario, 0.0, policy)]
            interval = row["paired_normal_95_interval"]
            lines.append(f"| {SCENARIOS[scenario]} | {NAMES[policy]} | {100*row['delta_vs_scalar_mean']:.2f} | "
                         f"[{100*interval[0]:.2f}, {100*interval[1]:.2f}] | {row['active_mean']:.2f} + {row['shadows_mean']:.2f} | "
                         f"{row['payload_bytes_mean']:.0f} |")
    lines.extend(["", "`payload_bytes` mede a serialização JSON dos episódios retidos, não tamanho de arquivo SQLite ou RAM real.",
        "Os tetos são iguais em episódios totais, mas ocupação, bytes e admissão realizados diferem e são reportados.",
        "As diferenças entre A1 e sua ablação sem amplificação também mudam a faixa literal de arquivamento de sombras.",
        "Portanto, essa ablação mede um efeito composto sobre urgência e elegibilidade de sombras, não aumento isolado de informação.",
        "A retirada das sombras reduz também o orçamento total; sua diferença não isola apenas o método de recuperação.", "",
        "## Limites", "",
        "Vetores aleatórios permitem recuperar episódios cuja direção foi preservada; não medem compreensão, verdade ou geração de linguagem.",
        "Erros de roteamento da ingestão são simulados; consultas recebem o domínio verdadeiro. Não há encoder treinado ou avaliação de texto real.",
        "O foco conhecido favorece tanto A1 quanto o FIFO especializado. Essa informação a priori é parte explícita do protocolo.",
        "A avaliação não esgota controladores possíveis nem substitui um benchmark externo. Não houve treino LoRA, geração REM ou validação de consciência.", "",
        "## Reprodução", "", "```bash", "python tools/validate.py --full-benchmark", "```", "",
        f"Validação local: **{VALIDATION['test_count']} testes aprovados** em Python {VALIDATION['python']}.",
        "O workflow GitHub foi configurado, mas não foi executado remotamente nesta entrega.", ""])
    (ROOT/"docs/RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def make_figure():
    policies = ["scalar_mean", "A1_fixed", "A3_context", "quota_fifo"]
    color_list = ["#667587", "#2b72a8", "#2f8f78", "#b47437"]
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":9, "axes.spines.top":False,
                         "axes.spines.right":False, "axes.grid":True, "grid.alpha":0.15,
                         "axes.axisbelow":True})
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.7), sharey=True)
    for ax, error in zip(axes, (0.0, 0.2)):
        for i, (policy, color) in enumerate(zip(policies, color_list)):
            values = [SUMMARY[(s, error, policy)]["recall_mean"]*100 for s in SCENARIOS]
            sds = [SUMMARY[(s, error, policy)]["recall_sd"]*100 for s in SCENARIOS]
            positions = [j+(i-1.5)*0.19 for j in range(3)]
            ax.bar(positions, values, width=0.18, color=color, label=NAMES[policy],
                   yerr=sds, error_kw={"elinewidth":0.65, "capsize":2})
        ax.set_xticks([0,1,2], ["Focado", "Troca", "Difuso"])
        ax.set_title(f"Roteamento: {int(error*100)}% de erro", fontweight="bold", loc="left")
        ax.set_ylim(0, 106)
        ax.set_yticks(range(0,101,20))
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Recall@1 (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5,-0.025))
    fig.tight_layout(rect=(0,0.12,1,1))
    path = ROOT/"validation/retrieval_comparison.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def build_pdf(output, figure):
    pdfmetrics.registerFont(TTFont("DV", findfont(FontProperties(family="DejaVu Sans"))))
    pdfmetrics.registerFont(TTFont("DVB", findfont(FontProperties(family="DejaVu Sans", weight="bold"))))
    pdfmetrics.registerFont(TTFont("DVM", findfont(FontProperties(family="DejaVu Sans Mono"))))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DVB", italic="DV", boldItalic="DVB")
    navy = colors.HexColor("#15354a")
    blue = colors.HexColor("#276d91")
    gray = colors.HexColor("#536474")
    light = colors.HexColor("#edf3f7")
    styles = {
        "body": ParagraphStyle("body", fontName="DV", fontSize=9.1, leading=14.1, textColor=navy, spaceAfter=8),
        "small": ParagraphStyle("small", fontName="DV", fontSize=7.7, leading=11.2, textColor=gray, spaceAfter=6),
        "h1": ParagraphStyle("h1", fontName="DVB", fontSize=19, leading=23, textColor=navy, spaceAfter=13),
        "h2": ParagraphStyle("h2", fontName="DVB", fontSize=11.2, leading=15, textColor=blue, spaceBefore=9, spaceAfter=6),
        "title": ParagraphStyle("title", fontName="DVB", fontSize=34, leading=40, textColor=navy, spaceAfter=16),
        "sub": ParagraphStyle("sub", fontName="DV", fontSize=17, leading=23, textColor=blue, spaceAfter=16),
        "eq": ParagraphStyle("eq", fontName="DVM", fontSize=8.4, leading=13, textColor=navy,
                             backColor=light, borderPadding=9, spaceBefore=7, spaceAfter=12),
        "cell": ParagraphStyle("cell", fontName="DV", fontSize=8, leading=11.5, textColor=navy),
        "th": ParagraphStyle("th", fontName="DVB", fontSize=8, leading=11.5, textColor=colors.white),
    }
    story = []

    def p(text, style="body"):
        story.append(Paragraph(text, styles[style]))

    def eq(text):
        p(escape(text).replace("\n", "<br/>"), "eq")

    def table(rows, widths, *, header=True):
        cells = [[Paragraph(escape(str(value)), styles["th" if index == 0 and header else "cell"])
                  for value in row] for index, row in enumerate(rows)]
        tab = Table(cells, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [("VALIGN",(0,0),(-1,-1),"TOP"), ("LEFTPADDING",(0,0),(-1,-1),7),
                    ("RIGHTPADDING",(0,0),(-1,-1),7), ("TOPPADDING",(0,0),(-1,-1),7),
                    ("BOTTOMPADDING",(0,0),(-1,-1),7),
                    ("LINEBELOW",(0,0),(-1,0),0.5,navy)]
        if header:
            commands += [("BACKGROUND",(0,0),(-1,0),navy),
                         ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, light])]
        tab.setStyle(TableStyle(commands))
        story.append(tab)
        story.append(Spacer(1,9))

    def page(title, number):
        if story:
            story.append(PageBreak())
        p(f"{number:02d} / ANÁLISE E IMPLEMENTAÇÃO", "small")
        p(title, "h1")

    p("SOFTWARE DE PESQUISA • 11 NOVEMBRO 2026", "small")
    story.append(Spacer(1,17))
    p("VAL", "title")
    p("Análise crítica e referência<br/>executável para publicação", "sub")
    p("<b>Valued Asymmetric Lambda</b><br/>Proposta arquitetural: Cleilson Elias de Sousa<br/>Referência de software: versão 0.1.0", "body")
    story.append(Spacer(1,12))
    p("Parecer: publicável como software experimental", "h2")
    p("O núcleo de VAL pode ser executado e testado: um vetor de limiares por domínio decide quais episódios entram na memória. A entrega inclui implementação nova, persistência, testes e comparações reproduzíveis. A formulação original exige revisão antes de sustentar superioridade geral, equivalência biológica ou medidas de consciência.")
    table([["Resultado desta entrega", "Conclusão permitida"],
           [f"{VALIDATION['test_count']} testes locais aprovados", "Funcionamento das regras, limites e persistência examinados pelos testes."],
           ["336 execuções sintéticas", "Ganho depende da tarefa, roteamento, alocação e política de memória."],
           ["FIFO por cotas vence no cenário focado", "Não se demonstrou vantagem de VAL sobre alocação simples nesse cenário."],
           ["A3 responde a contexto externo", "Adaptação autônoma e motivação intrínseca continuam em aberto."]], [190,305])
    p("Escopo e origem", "h2")
    p("Leitura integral do PDF fornecido (19 páginas), datado de 10/05/2026. O pacote foi escrito a partir dessa especificação, com assistência de IA; não é recuperação certificada de código experimental original. O PDF original não é redistribuído.")
    p("Código sob licença MIT, seguindo o padrão das entregas anteriores. A licença cobre os novos arquivos de software e documentação; não altera os direitos do artigo original ou de terceiros.", "small")

    page("O mecanismo que pode ser implementado", 2)
    p("Seleção por domínio", "h2")
    eq("theta_k = theta_min + (theta_max-theta_min)*lambda_k       (1)\nG(x,k) = 1 se h(x) > theta_k; 0 caso contrario")
    p("A rota dominante escolhe qual λ será usado. Com todos os componentes iguais, recupera-se o portão escalar. Empates de rota seguem o menor índice. O software preserva a desigualdade estrita: λ=0 não aceita um score abaixo de θ_min e λ=1 não bloqueia um score maior que θ_max.")
    p("Score e representação", "h2")
    eq("H_R = -2*sum_i p_i*(1-p_i)*log2(p_i)                      (2)\nh = H_R/(2*log2(K)); para K=1, h=0")
    p("A fórmula compatível com o LLI-CAMS é uma soma sobre pares fora da diagonal, cuja massa não é normalizada. Para quatro afinidades uniformes, h=0,75. O host pode fornecer outro score em [0,1]; nesse caso, precisa validar sua interpretação. Distribuição de rota, relevância e verdade são variáveis distintas.")
    p("Dinâmica e amplificação", "h2")
    eq("M_k[n] = exp(-beta_k*dt)*M_k[n-1] + alpha_k*G*h*x_hat     (3)\nh_eff,k = h*[1+(1-lambda_k)*delta_max]                      (4)")
    p("A consolidação usa impulsos e o decaimento exponencial entre eventos. α e β são iguais entre domínios por padrão; a relação opcional com λ é uma escolha de engenharia separada. O multiplicador de (4) é literal, mas não demonstra ganho de informação: com λ=0,05 e δ_max=0,9, o fator 1,855 resulta da substituição dos parâmetros.")
    p("Recuperação e linha de base", "h2")
    eq("Omega(q,k) = sigmoid(a*[h_eff(q,k)-baseline_eff,k])        (5)\nrecuperar sombra se cos(q,s)*Omega(q,k) > delta_res")
    p("A média EMA é armazenada na escala bruta e reescalada pelo λ atual, evitando surpresa artificial só pela mudança de escala. A consulta usa a história anterior e não modifica o estado. Na própria média calibrada, Ω=0,5 para qualquer λ.")

    page("Auditoria das equações e das alegações", 3)
    table([["Local", "Problema identificado", "Tratamento no software"],
           ["VAL-2", "Taxas, discretização e relação memória/grafo não estão determinadas.", "Impulsos, decaimento exato e grafo explícito; taxas iguais por padrão."],
           ["VAL-4", "ρ/λ é singular em zero; f e medida de consciência não estão definidas.", "Nenhum C de consciência é calculado."],
           ["VAL-5", "Amplificação escolhida não é uma constante neurofisiológica.", "Score rotulado como multiplicado; δ_max não calibrado."],
           ["VAL-6", "Maior média acompanha maior score; baixa λ não garante urgência elevada.", "Referência por domínio na mesma unidade do score atual."],
           ["VAL-7", "Portão bruto e intervalo efetivo deixam uma faixa sem destino.", "Política literal por padrão; alternativa raw_interval identificada."],
           ["VAL-8", "Produto de marginais exige independência; evento conjunto não excede cada marginal.", "Evento conjunto observado, sem produto de probabilidades."],
           ["VAL-9/10", "-grad(V) reduz valor se V for recompensa; indicador não fornece gradiente usual útil.", "Ascensão projetada em V-K; gradientes fornecidos pelo host."],
           ["VAL-11", "Ranks singulares, não inteiros e sem orçamento.", "Piso de λ, teto inteiro, orçamento e status de treino não executado."],
           ["VAL-12", "Temperatura baixa não prova insight ou exploração adequada.", "Agenda com piso; nenhuma geração executada."],
           ["Seção 10", "μ=0 produz metade do baseline; não define aprendizagem ou competição.", "Motivação autônoma não é anunciada como resolvida."]], [62,220,213])
    p("Correção explícita da adaptação", "h2")
    eq("Lambda[n+1] = clip(Lambda[n] + eta*(grad V-grad K), 0, 1)  (6)")
    p("A equação (6) maximiza V-K ou minimiza L=-V+K. O host deve definir utilidade, custo e estimador de gradiente. Uma simples troca de sinal não resolve o aprendizado através de um portão binário nem cria motivação intrínseca.")
    p("Não há evidência fornecida para reproduzir os fatores 3,8x, sombras/ativos>10:1 ou aumentos de Eureka em ordens de magnitude como constantes gerais. Eles precisam de condições, protocolo e dados.", "small")

    page("Contraexemplos e uma proposição corrigida", 4)
    p("1. A superioridade global pode inverter", "h2")
    p("Dois domínios: Λ=(0,05;0,95), média escalar 0,5, θ_min=0,1 e θ_max=0,9. Duas entradas de score 0,6 no segundo domínio, com vetores colineares, são rejeitadas pelo VAL (θ=0,86) e aceitas pelo escalar (θ=0,5). A densidade ativa é 0 versus 1, e a soma ρ/λ é 0 versus 2. Para f crescente e termo de sombra zero ou suficientemente pequeno, a desigualdade geral alegada não vale.")
    p("2. Mais memórias não implica maior densidade", "h2")
    p("Duas memórias conectadas têm densidade 1. A adição de uma memória isolada reduz E/[N(N-1)/2] para 1/3. Contagem e densidade não são intercambiáveis. Com ρ_k∈[0,1] e regularizador ε>0, o proxy Σρ_k/max(λ_k,ε) tem teto K/ε; não diverge indefinidamente.")
    p("3. Urgência e probabilidade não crescem por definição", "h2")
    p("Na média calibrada, Ω=0,5 independentemente de λ. Para eventos A e B, P(A∩B)≤min[P(A),P(B)]. Compartilhar a consulta torna a independência uma hipótese adicional. Nenhuma dessas propriedades fornece uma prova de mais insights úteis.")
    p("4. Sombras não precisam superar ativos", "h2")
    ratio = AUDIT["uniform_score_shadow_ratio"]["shadow_to_active"]
    p(f"Sob score uniforme em [0,1], λ=0,05 e os parâmetros literais, o fluxo ativo é 0,86 e o fluxo de sombras é cerca de 0,07224. A razão é {ratio:.3f}, muito abaixo de 10. É um contraexemplo matemático; não uma taxa biológica. Estoque retido e fluxo de admissão também são medidas diferentes.")
    p("Uma proposição realmente demonstrável", "h2")
    eq("P(G=1|k) = 1-F_k(theta(lambda_k))                         (7)")
    p("Com score fixo, distribuição F_k e limiar crescente em λ, diminuir λ não reduz a probabilidade de admissão. A prova segue da monotonicidade da função de distribuição. Para concluir ganho de desempenho, faltam hipóteses sobre utilidade dos scores, erros de rota, competição por memória e relevância futura. Essa é a base adequada para uma conjectura condicional.")
    p("Reprodução: execute val audit. Todos os exemplos ficam em validation/counterexamples.json, com entradas e valores numéricos.", "small")

    page("Fundamento científico e fronteira da evidência", 5)
    p("As fontes apoiam motivação e analogias de modelagem. Elas não identificam λ por domínio como variável neural, não derivam 1/λ como profundidade de consciência e não validam os parâmetros numéricos do software.")
    table([["Fonte verificada", "Acesso nesta análise", "Uso permitido"],
           ["Carson, Peterson e Higgins (2003)", "Resumo bibliográfico no PubMed.", "Associação entre inibição latente e realização criativa em amostras de alto QI; não causalidade ou calibração de λ."],
           ["Dwyer et al. (2024)", "Texto integral disponível na editora; resumo e enquadramento examinados.", "Hiperfoco e desatenção relacionados em questionários; experiências favoráveis e desfavoráveis; não portão neural identificado."],
           ["Snyder (2009)", "Texto integral disponível no PMC; formulação da hipótese examinada.", "Hipótese de acesso a informação menos processada por desinibição; não prova de capacidade pronta em qualquer rede."]], [135,150,210])
    p("Como revisar o texto original", "h2")
    p("O manuscrito trata algumas hipóteses como fatos estabelecidos e algumas relações escolhidas como consequências necessárias da neurociência. A versão de publicação deve distinguir inspiração biológica, definição computacional, dedução matemática e resultado experimental. Perfis humanos diversos não são equivalentes a um vetor de parâmetros.")
    p("Substituir o enunciado de superioridade universal por uma proposição restrita ou conjectura evita apoiar toda a arquitetura em uma conclusão que os próprios contraexemplos invalidam. Isso preserva a ideia útil: investigar controle seletivo de memória sob restrições mensuráveis.")
    p("Referências consultadas", "h2")
    p("Carson, S. H.; Peterson, J. B.; Higgins, D. M. (2003). <i>Decreased latent inhibition is associated with increased creative achievement in high-functioning individuals.</i> JPSP 85(3), 499-506. DOI: 10.1037/0022-3514.85.3.499. <link href='https://pubmed.ncbi.nlm.nih.gov/14498785/' color='#276d91'>PubMed</link>.", "small")
    p("Dwyer, P. et al. (2024). <i>A trans-diagnostic investigation of attention, hyper-focus, and monotropism in autism, attention dysregulation hyperactivity development, and the general population.</i> Neurodiversity. DOI: 10.1177/27546330241237883. <link href='https://journals.sagepub.com/doi/full/10.1177/27546330241237883' color='#276d91'>Editora</link>.", "small")
    p("Snyder, A. (2009). <i>Explaining and inducing savant skills: privileged access to lower level, less-processed information.</i> Phil. Trans. R. Soc. B 364, 1399-1405. DOI: 10.1098/rstb.2008.0290. <link href='https://pmc.ncbi.nlm.nih.gov/articles/PMC2677578/' color='#276d91'>Texto integral no PMC</link>.", "small")
    p("Fonte interna: de Sousa, C. E. (2026). VAL, PDF fornecido, 19 páginas. Contexto de implementação: <link href='https://github.com/CleilsonElias/LLI-CAMS/blob/main/docs/FORMALISM.md' color='#276d91'>LLI-CAMS / FORMALISM.md</link>, consultado em 11/11/2026. A compatibilidade de bancos e integração com o LLI-CAMS não foram testadas.", "small")

    page("Experimento sintético reproduzível", 6)
    p("O protocolo usa 8 sementes, 3 cenários, 2 níveis de erro de roteamento (0% e 20%) e 7 políticas: 336 execuções. Cada execução contém 320 fatos com vetores aleatórios de 12 dimensões e 48 consultas perturbadas. Códigos factuais são recuperáveis apenas quando o episódio correto permanece no acervo. O score de admissão é fornecido, sintético e independente do rótulo de relevância.")
    p("Os dados e consultas são idênticos entre políticas em cada condição. Há teto de 64 ativos + 64 sombras; o FIFO por cotas usa o mesmo orçamento total de 128 episódios como ativos. A ablação sem sombras tem apenas 64 slots. Bytes e ocupação realizados são reportados; não são presumidos iguais.")
    p("Recall@1 médio, sem erro de roteamento", "h2")
    rows = [["Política", "Focado", "Troca", "Difuso"]]
    for policy in NAMES:
        rows.append([NAMES[policy], *[percent(SUMMARY[(s,0.0,policy)]["recall_mean"]) for s in SCENARIOS]])
    table(rows, [237,86,86,86])
    story.append(Image(str(figure), width=495, height=190, kind="proportional"))
    p("Figura 1. Médias e desvio padrão entre sementes para quatro comparadores. O painel direito introduz 20% de erros no domínio da ingestão. Não há inferência sobre uma população de tarefas humanas ou de linguagem natural.", "small")

    page("O que os resultados permitem concluir", 7)
    p("Seleção focalizada funciona neste teste, mas não identifica um benefício exclusivo de VAL", "h2")
    p("No cenário focado sem erro de rota, A1 obtém 67,97% contra 42,71% do escalar. Entretanto, o FIFO por cotas totais chega a 100% com a mesma informação a priori sobre o domínio relevante. Isso mostra que alocação simples já resolve melhor esse cenário. Não se pode atribuir o efeito especificamente à amplificação ou ao formalismo completo.")
    p("Mudança de tarefa exige um mecanismo que saiba realocar o foco", "h2")
    p("Após a troca, A1 fixo obtém 57,81% contra 61,20% do escalar. A3 chega a 92,45% quando o domínio-alvo é explicitamente informado; esse sinal favorece a política e não foi aprendido. Na consulta difusa, A1 obtém 38,28% contra 39,32% do escalar, uma diferença pequena neste conjunto.")
    p("Variabilidade e armazenamento realizados", "h2")
    rows = [["Condição / política", "Δ escalar (p.p.)", "Intervalo descritivo", "Payload (bytes)"]]
    for scenario, policy in (("focused","A1_fixed"),("focused","quota_fifo"),
                             ("shifted","A1_fixed"),("shifted","A3_context"),("diffuse","A1_fixed")):
        row = SUMMARY[(scenario,0.0,policy)]
        low, high = row["paired_normal_95_interval"]
        rows.append([f"{SCENARIOS[scenario]} / {NAMES[policy]}", f"{100*row['delta_vs_scalar_mean']:+.2f}",
                     f"[{100*low:+.2f}; {100*high:+.2f}]", f"{row['payload_bytes_mean']:.0f}"])
    table(rows, [190,85,126,94])
    p("Intervalos = média das diferenças pareadas ±1,96·s/√8. São resumos descritivos entre sementes, sem garantia de calibração populacional ou correção para múltiplas comparações. Payload é a serialização JSON dos episódios retidos, não RAM ou tamanho do SQLite.", "small")
    p("Limitações das ablações", "h2")
    p("Retirar amplificação altera tanto a urgência quanto a faixa literal de arquivamento: não isola ganho de informação. Retirar sombras reduz também o orçamento total. O benchmark não tem encoder real, texto com relevância rotulada, aprendizagem autônoma, verificação factual, LoRA ou geração REM. Ele testa recuperação episódica sob regras e recursos explícitos.")
    p("Próximo experimento discriminante", "h2")
    p("Usar corpus real com consultas separadas em calibração e avaliação; comparar relevância, cotas e VAL sob o mesmo orçamento em bytes; medir tarefas periféricas, abstenção e mudança de foco; só então avaliar A3 aprendido e integração paramétrica. O ganho precisa sobreviver a comparadores simples.")

    page("Entrega, validação e caminho para publicação", 8)
    table([["Entregue", "Estado verificável"],
           ["Núcleo Python sem dependências de execução", "λ por domínio, portões, massa, sombras, grafo, consulta e gradientes externos."],
           ["SQLite / CLI / API Python", "JSON versionado, revisão esperada e conflito de escrita; consulta e plano somente leitura."],
           ["Planejamento offline", "Clusters de sombras, ranks limitados e agenda REM; treino e geração não executados."],
           ["Documentação e proveniência", "MIT, CITATION.cff, NOTICE, formalismo, auditoria, integração e publicação."],
           ["Validação", f"{VALIDATION['test_count']} testes locais; benchmark completo; contraexemplos e logs incluídos."]], [185,310])
    p("Executar e revisar", "h2")
    eq("python -m pip install -e .\npython -m unittest discover -s tests -v\nval demo --output val_demo\nval audit\npython tools/validate.py --full-benchmark")
    p("O núcleo executa em CPU e não exige GPU ou serviços pagos. O pacote é independente: a aplicação fornece embeddings, scores e roteamento. A integração com o banco do LLI-CAMS continua pendente. O workflow foi preparado para Python 3.11-3.13; a execução local documentada usa Python 3.12.")
    p("Decisão de publicação", "h2")
    p("Publicar como <b>VAL Reference v0.1.0</b>, software experimental de seleção e recuperação de memória. A release deve incluir resultados desfavoráveis, status real de LoRA/REM e limites do teorema. O diretório e o wheel foram preparados para distribuição; o envio a um novo repositório GitHub não foi efetuado nesta etapa.")
    p("Rastreabilidade do documento de origem", "h2")
    sha = PROVENANCE["sha256"]
    p("SHA-256 do PDF recebido:<br/><font face='DVM' size='7.2'>"+sha[:32]+"<br/>"+sha[32:]+"</font>", "small")
    p("Nenhum código original de experimento, conjunto de dados, checkpoint ou log do manuscrito foi fornecido. Esta entrega permite investigar a hipótese com honestidade; não converte previsões teóricas em resultados observados.", "small")

    def decorate(canvas, doc):
        width, height = A4
        canvas.setStrokeColor(colors.HexColor("#d4e0e8"))
        canvas.setLineWidth(0.6)
        canvas.line(20*mm, height-16*mm, width-20*mm, height-16*mm)
        canvas.setFont("DV",7.2)
        canvas.setFillColor(gray)
        canvas.drawString(20*mm, height-12*mm, "VAL • AUDITORIA TÉCNICO-CIENTÍFICA • v0.1.0")
        canvas.line(20*mm, 16*mm, width-20*mm, 16*mm)
        canvas.drawString(20*mm, 11*mm, "11/11/2026 | Referência experimental | Cleilson Elias de Sousa")
        canvas.drawRightString(width-20*mm, 11*mm, str(doc.page))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(output), pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                          topMargin=23*mm, bottomMargin=22*mm,
                          title="VAL - Análise crítica e implementação de referência v0.1.0",
                          author="Cleilson Elias de Sousa; análise e implementação assistidas por IA")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, leftPadding=0,
                  rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="audit", frames=[frame], onPage=decorate))
    doc.build(story)


if __name__ == "__main__":
    build_results()
    figure_path = make_figure()
    output_path = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT.parent/"output/pdf/Analise_VAL_2026-11-11.pdf"
    build_pdf(output_path, figure_path)
    print(output_path)
