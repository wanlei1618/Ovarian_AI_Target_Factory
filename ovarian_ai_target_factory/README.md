# Ovarian AI Target Factory MVP

This MVP creates the project skeleton, keeps data and outputs on `D:/Ovarian_AI_Target_Factory`, and generates a mock daily evidence report without downloading large public datasets.

## Run on Windows

```powershell
cd D:\Ovarian_AI_Target_Factory\ovarian_ai_target_factory
python scripts\run_daily_pipeline.py
```

## Main outputs

- `D:/Ovarian_AI_Target_Factory/results/daily_reports/literature_digest_YYYYMMDD.json`
- `D:/Ovarian_AI_Target_Factory/results/daily_reports/new_dataset_registry_YYYYMMDD.tsv`
- `D:/Ovarian_AI_Target_Factory/results/daily_reports/Daily_Ovarian_AI_Target_Report_YYYYMMDD.md`
- `D:/Ovarian_AI_Target_Factory/results/daily_reports/logs/*.log`

MVP v0.1 queries PubMed and GEO metadata only. TCGA, DepMap, single-cell matrices, and spatial matrices are intentionally not downloaded.
