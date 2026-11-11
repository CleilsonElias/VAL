# Integração com uma aplicação de memória ou LLM

Veja também [o impacto entre projetos](CROSS_PROJECT_IMPACT.md). VAL 0.2.0
adota `raw_interval` em novas configurações; snapshots com a política explícita
`paper` mantêm o comportamento legado. λ de admissão e λ de aprendizado CALMS
não são o mesmo parâmetro e não têm os mesmos intervalos.

O host mantém seu encoder fixo, calcula afinidades por domínio e define um score
de seleção. Passe esses dados por `Observation` e consulte os trechos recuperados
antes da geração de resposta. Preserve origem e evidência fora da pontuação:
H_R e λ não verificam se um fato é verdadeiro. Consultas retornam registros;
o VAL não gera respostas em linguagem natural.

O exemplo `examples/host_integration.py` utiliza vetores fictícios. Para encoder
real, registre nome, versão, dimensão, normalização e hash do modelo no host.
O controlador valida a dimensão; não detecta dois modelos distintos que geram
vetores de mesma dimensão. Mudar o encoder exige nova memória ou reindexação.

A fórmula de H_R foi verificada contra `docs/FORMALISM.md` do repositório
LLI-CAMS acessado em 11/11/2026. Esse compartilhamento matemático não garante
compatibilidade de schema ou integração das fases offline. Nenhuma integração
binária ou de banco com o LLI-CAMS foi testada nesta entrega.

```python
from val_memory import SQLiteStore

store = SQLiteStore("memory.sqlite")
memory, revision = store.load()
# memory.observe(observation_validada_pelo_host)
new_revision = store.save(memory, expected_revision=revision)
```

Crie inicialmente o banco com `store.save(nova_memoria, expected_revision=0)`.
Em `RevisionConflict`, recarregue o estado e reaplique a operação de domínio;
não remova o controle de revisão nem sobrescreva o estado concorrente.

O adaptador A3 recebe derivadas de uma utilidade definida pelo host. Um ciclo
experimental sério separa calibração e avaliação, controla custo de memória e
preserva avaliações de tarefas periféricas. Os gradientes podem ser negativos:
se reduzir λ aumenta V, então dV/dλ<0 e a atualização deve reduzir λ.

O planejamento offline é inspecionável e somente leitura. Treinar LoRA exige
integrar um backend real, usar evidências autorizadas, dimensionar cada rank por
camada e medir interferência em tarefas antigas. Nesta versão, `phase_II.status`
é sempre `not_run`; não existem checkpoints fictícios ou pesos alterados.
