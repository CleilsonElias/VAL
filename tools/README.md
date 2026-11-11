# Ferramentas de validação e relatório

O núcleo e os testes usam somente Python e sua biblioteca padrão.

```bash
python tools/validate.py --full-benchmark
```

Esse comando reexecuta testes, exemplo, contraexemplos e benchmark, e atualiza
os registros em `validation/`. Use um checkout separado para preservar o registro
da release original. Versão de Python e plataforma são registradas na execução.

O relatório e a figura são uma etapa opcional com dependências próprias:

```bash
python -m pip install matplotlib reportlab
python tools/make_report.py caminho_do_relatorio.pdf
```

O script usa as fontes DejaVu disponíveis por meio do Matplotlib. Ele recria
`docs/RESULTS.md` e `validation/retrieval_comparison.png` a partir dos resultados
locais. A auditoria narrativa corresponde ao manuscrito de 10/05/2026; mudanças
no formalismo ou no protocolo exigem revisão do texto antes de reutilização.

O PDF não exige essas dependências para leitura, e elas não são dependências
da distribuição `val-reference`.

`make_report.py` is the historical 0.1.0 audit report generator, not the source
of the revised manuscript or 0.2.0 validation. The current primary study is
`studies/manuscript_revision/`; use `verify_frozen_study.py` for exact hashes.
