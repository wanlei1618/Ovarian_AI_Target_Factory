# Codex 首批执行任务清单

## Batch 0：安全初始化

- [ ] 创建 `ovarian_ai_target_factory/` 项目结构
- [ ] 创建 `config/paths.yaml`，默认数据根目录为 `D:/Ovarian_AI_Target_Factory`
- [ ] 创建 `src/ovarian_ai/utils/paths.py`
- [ ] 创建 `R/utils_paths.R`
- [ ] 创建 `scripts/initialize_project.py`
- [ ] 创建 `scripts/check_disk_usage.py`
- [ ] 测试 D 盘目录创建
- [ ] 确认没有任何大文件写入 C 盘

## Batch 1：每日文献/数据雷达

- [ ] 实现 `literature_watcher.py`
- [ ] 实现 `dataset_watcher.py`
- [ ] 实现 `report_generator.py --mode daily`
- [ ] 生成第一份 `daily_evidence_report.md`

## Batch 2：TCGA-OV 主干分析

- [ ] 实现 `R/01_tcga_ov_pipeline.R`
- [ ] 输出表达、生存、CNV、甲基化 summary
- [ ] 生成初版候选基因表

## Batch 3：DepMap 功能依赖

- [ ] 实现 `depmap_pipeline.py`
- [ ] 筛选 ovarian cancer cell lines
- [ ] 输出 dependency summary

## Batch 4：单细胞/空间验证

- [ ] 实现 `R/04_scrna_validation_pipeline.R`
- [ ] 实现 `R/05_spatial_validation_pipeline.R`
- [ ] 输出靶点细胞定位和空间生态位证据

## Batch 5：评分和 Target Card

- [ ] 实现 `target_scoring.py`
- [ ] 实现 `target_card.py`
- [ ] 生成 `candidate_target_table.tsv`
- [ ] 生成 Top 20 Target Cards
- [ ] 生成 `weekly_evidence_report.md`
