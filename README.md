# VAL — Valued Asymmetric Lambda

**Versão 0.2.0 · software experimental de pesquisa · Python 3.11+ · MIT**

Controlador de memória externa com inibição por domínio, pools limitados de
ativos e sombras, urgência calibrada e persistência SQLite. Arquitetura de
**Cleilson Elias de Sousa**. Não exige GPU, modelos baixados ou chaves de API.
A aplicação hospedeira fornece embeddings, roteamento e scores.

Inclui o artigo revisado
[VAL for Domain Selective Memory Admission and Retrieval](docs/VAL_Revised_Manuscript_2026-11-11.pdf)
([Word editável](docs/VAL_Revised_Manuscript_2026-11-11.docx)). A revisão delimita
as proposições e substitui alegações amplas por testes e contraexemplos.
O código não demonstra consciência, savantismo, criatividade ou segurança de LLMs.

## Executar

```bash
python -m venv .venv
```

Linux/macOS: `source .venv/bin/activate`.
Windows PowerShell: `.venv\Scripts\Activate.ps1`.

```bash
python -m pip install -e .
val demo --output val_demo
val inspect --state val_demo/memory.sqlite
val query --state val_demo/memory.sqlite --vector "[1,0,0,0]" --routing "[1,0,0,0]" --entropy 0.8
val plan --state val_demo/memory.sqlite --output val_demo/new_plan.json
```

Sem instalação, troque `val` por `python run_val.py`. A CLI recusa sobrescritas.
Todos os dados do exemplo são fictícios.

```python
from val_memory import Observation, VALConfig, VALMemory

memory = VALMemory(VALConfig(("matematica", "biologia", "outros"), (0.05, 0.10, 0.90)))
decision = memory.observe(Observation(
    "exemplo-1", "Representação fictícia de metabolismo por grafos.",
    vector=(0.8, 0.5, 0.1), routing=(0.45, 0.5, 0.05), entropy=0.6,
))
print(decision)
print(memory.query((0.8, 0.5, 0.1), (0.45, 0.5, 0.05), entropy=0.7))
```

Para JSONL próprio:

```bash
val ingest --config examples/config.json --input examples/observations.jsonl --state minha_memoria.sqlite
```

Observações contêm `id`, `text`, `vector`, `routing` e `entropy` opcional em [0,1].
Vetores devem pertencer ao mesmo encoder fixo, cuja identidade é garantida pelo
host. Sem score explícito, calcula-se H_R normalizado a partir do roteamento.
Entropia de roteamento não verifica relevância, utilidade ou verdade.

## Regra revisada

| Operação | Comportamento |
|---|---|
| Admissão ativa | Score bruto `h > theta_k` |
| Arquivo de rejeitados | `shadow_global*lambda_k < h <= theta_k` |
| Padrão novo | `shadow_policy="raw_interval"` |
| Regra antiga | Disponível explicitamente como `shadow_policy="paper"` |
| Adaptação | Ascensão projetada de utilidade líquida com gradientes externos |
| LoRA/REM | Planejamento; treino e geração não executados |

A regra coerente elimina uma faixa de descarte causada pelo uso de score bruto
na admissão e amplificado no arquivo. Estados antigos que salvaram explicitamente
`paper` mantêm a política. Exemplo legado: `examples/config_legacy.json`.

Leia o [formalismo](docs/FORMALISM.md), a [integração](docs/INTEGRATION.md) e a
[análise de impacto](docs/CROSS_PROJECT_IMPACT.md). LLI-CAMS preserva sua execução;
CALMS-SAVANT recebe uma correção numérica de saturação. Os parâmetros λ têm
funções e intervalos diferentes nesses projetos; não há migração automática.

## Evidência executada

O [estudo revisado](studies/manuscript_revision/README.md) contém **864 execuções**:
16 sementes, três cenários, dois níveis de erro e nove políticas. Fatos, scores
e alvos são pareados entre níveis de erro. O teto é de 128 episódios; ocupação
e bytes realizados são reportados separadamente.

| Recall@1, sem erro de rota | Foco | Mudança de alvo |
|---|---:|---:|
| Limiar uniforme coerente | 39,91% | 64,91% |
| VAL seletivo fixo coerente | 73,83% | 55,99% |
| VAL adaptativo com contexto externo | 73,83% | 96,68% |
| Cotas fixas | 99,09% | 33,01% |
| Cotas adaptativas com o mesmo contexto | 99,09% | 100,00% |

A alocação por domínio ajuda em certas condições, mas cotas simples obtêm
resultados maiores. A ablação coerente não mede benefício de Recall@1 da
amplificação. O contexto adaptativo é externo, não motivação aprendida.
Vetores e scores são sintéticos; não houve treinamento de LLM.

## Testar e reproduzir

```bash
python -m unittest discover -s tests -v
val audit --output contraexemplos.json
python studies/manuscript_revision/experiments/check_revision.py -v
python studies/manuscript_revision/experiments/revision_benchmark.py --output nova_execucao.json
```

44 testes do pacote e seis verificações do suplemento passaram localmente.
O estudo mantém seu núcleo **0.1.0 congelado**, com políticas explícitas; seus
resultados não são reatribuídos ao novo padrão. CI configura Python 3.11–3.13.
`val benchmark` preserva o estudo histórico exploratório, que tem limitações
de pareamento entre níveis de erro e não fundamenta os resultados revisados.

[Resultados e limites](docs/RESULTS.md) · [auditoria original](docs/SCIENTIFIC_AUDIT.md)
· [mapa das correções](studies/manuscript_revision/MAPA_DAS_CORRECOES.md)

Código e documentação nova são MIT. Os direitos dos manuscritos e de artigos
de terceiros não são alterados; veja NOTICE.md e CITATION.cff.
