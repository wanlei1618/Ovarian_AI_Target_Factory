# Ovarian AI Target Factory：Codex 可执行项目需求文档

> 项目目标：为一名白天忙于临床工作的医生建立一套 **ChatGPT + Codex + 公共多组学/多模态数据库** 协同流水线，用于高效率、批量化、可迭代地发现卵巢癌候选靶点、机制轴和可验证课题。

---

## 0. 项目定位

本项目不是一次性生信分析，而是一个长期运行的“卵巢癌多组学靶点发现工厂”。

核心逻辑：

```text
Codex 负责：自动化检索、下载、清洗、建模、出图、生成报告
ChatGPT 负责：机制判断、证据整合、创新性判断、审稿人视角质疑、下一轮任务设计
医生本人负责：临床价值判断、资源可行性判断、最终选题拍板
```

项目首要目标：

1. 每日自动发现最新顶刊论文、预印本、数据集和方法学策略；
2. 每周自动更新卵巢癌候选靶点证据表；
3. 对每个候选靶点生成标准化 `Target Card`；
4. 将 bulk、CNV、甲基化、蛋白组、磷酸化、单细胞、空间转录组、DepMap/CRISPR、药敏和虚拟敲除证据整合成评分系统；
5. 让 ChatGPT 基于标准化结果判断最值得推进的机制轴与实验路线。

---

## 1. 强制数据存储规范：优先放在 D 盘，避免 C 盘拥堵

### 1.1 Windows 本地默认路径

Codex 在写任何下载、缓存、结果或中间文件脚本时，必须遵守：

```text
项目代码目录：D:\Ovarian_AI_Target_Factory\repo\ovarian_ai_target_factory
原始数据目录：D:\Ovarian_AI_Target_Factory\data_raw
处理后数据：D:\Ovarian_AI_Target_Factory\data_processed
结果目录：D:\Ovarian_AI_Target_Factory\results
缓存目录：D:\Ovarian_AI_Target_Factory\cache
日志目录：D:\Ovarian_AI_Target_Factory\logs
```

禁止默认把大文件写入：

```text
C:\Users\<username>\Downloads
C:\Users\<username>\Documents
C:\Users\<username>\AppData
C:\ProgramData
系统临时目录 C:\...
```

### 1.2 路径配置优先级

所有 Python/R 脚本必须按以下优先级确定数据根目录：

```text
1. 环境变量 OVARIAN_AI_DATA_ROOT
2. config/paths.yaml 中的 data_root
3. 如果是 Windows 且 D 盘存在，则默认 D:\Ovarian_AI_Target_Factory
4. 如果是 WSL 且 /mnt/d 存在，则默认 /mnt/d/Ovarian_AI_Target_Factory
5. 如果以上都不存在，才允许使用当前项目目录下的 ./local_data，并给出警告
```

### 1.3 Python 路径函数要求

Codex 必须在 `src/ovarian_ai/utils/paths.py` 中实现统一路径函数：

```python
from pathlib import Path
import os
import platform


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_data_root() -> Path:
    env_root = os.environ.get("OVARIAN_AI_DATA_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    config_path = get_project_root() / "config" / "paths.yaml"
    if config_path.exists():
        import yaml
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if cfg.get("data_root"):
            return Path(cfg["data_root"]).expanduser().resolve()

    if platform.system().lower().startswith("win") and Path("D:/").exists():
        return Path("D:/Ovarian_AI_Target_Factory").resolve()

    if Path("/mnt/d").exists():
        return Path("/mnt/d/Ovarian_AI_Target_Factory").resolve()

    fallback = get_project_root() / "local_data"
    print(f"[WARNING] D drive not found. Using fallback path: {fallback}")
    return fallback.resolve()


def ensure_subdirs() -> dict:
    root = get_data_root()
    subdirs = {
        "raw": root / "data_raw",
        "processed": root / "data_processed",
        "results": root / "results",
        "cache": root / "cache",
        "logs": root / "logs",
    }
    for p in subdirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return subdirs
```

### 1.4 R 路径函数要求

Codex 必须在 `R/utils_paths.R` 中实现：

```r
get_data_root <- function() {
  env_root <- Sys.getenv("OVARIAN_AI_DATA_ROOT", unset = NA)
  if (!is.na(env_root) && nzchar(env_root)) {
    return(normalizePath(env_root, winslash = "/", mustWork = FALSE))
  }

  config_path <- file.path(getwd(), "config", "paths.yaml")
  if (file.exists(config_path)) {
    if (!requireNamespace("yaml", quietly = TRUE)) {
      stop("Package 'yaml' is required to read config/paths.yaml")
    }
    cfg <- yaml::read_yaml(config_path)
    if (!is.null(cfg$data_root) && nzchar(cfg$data_root)) {
      return(normalizePath(cfg$data_root, winslash = "/", mustWork = FALSE))
    }
  }

  if (.Platform$OS.type == "windows" && dir.exists("D:/")) {
    return("D:/Ovarian_AI_Target_Factory")
  }

  if (dir.exists("/mnt/d")) {
    return("/mnt/d/Ovarian_AI_Target_Factory")
  }

  warning("D drive not found. Using ./local_data. Large downloads may occupy the current drive.")
  return(normalizePath("local_data", winslash = "/", mustWork = FALSE))
}

ensure_project_dirs <- function() {
  root <- get_data_root()
  dirs <- list(
    raw = file.path(root, "data_raw"),
    processed = file.path(root, "data_processed"),
    results = file.path(root, "results"),
    cache = file.path(root, "cache"),
    logs = file.path(root, "logs")
  )
  invisible(lapply(dirs, dir.create, recursive = TRUE, showWarnings = FALSE))
  return(dirs)
}
```

---

## 2. 推荐仓库目录结构

请 Codex 按以下结构创建项目：

```text
ovarian_ai_target_factory/
├── README.md
├── Makefile
├── pyproject.toml
├── environment.yml
├── renv.lock
├── .gitignore
├── config/
│   ├── paths.yaml
│   ├── search_terms.yaml
│   ├── journals.yaml
│   ├── datasets.yaml
│   ├── target_scoring.yaml
│   └── pipeline.yaml
├── prompts/
│   ├── 01_paper_summarizer.md
│   ├── 02_dataset_extractor.md
│   ├── 03_target_reviewer.md
│   ├── 04_codex_task_generator.md
│   ├── 05_reviewer_critique.md
│   └── 06_wetlab_validation_designer.md
├── src/
│   └── ovarian_ai/
│       ├── __init__.py
│       ├── utils/
│       │   ├── paths.py
│       │   ├── io.py
│       │   ├── logging_utils.py
│       │   └── schema.py
│       ├── literature/
│       │   ├── literature_watcher.py
│       │   ├── pubmed_client.py
│       │   ├── biorxiv_client.py
│       │   └── paper_ranker.py
│       ├── datasets/
│       │   ├── dataset_watcher.py
│       │   ├── geo_client.py
│       │   ├── sra_client.py
│       │   ├── cellxgene_client.py
│       │   ├── htan_client.py
│       │   └── tcia_client.py
│       ├── depmap/
│       │   └── depmap_pipeline.py
│       ├── scoring/
│       │   ├── target_scoring.py
│       │   └── target_card.py
│       ├── report/
│       │   └── report_generator.py
│       └── virtual_ko/
│           └── virtual_ko_pipeline.py
├── R/
│   ├── utils_paths.R
│   ├── utils_plot.R
│   ├── 01_tcga_ov_pipeline.R
│   ├── 02_bulk_validation_pipeline.R
│   ├── 03_cptac_ov_pipeline.R
│   ├── 04_scrna_validation_pipeline.R
│   ├── 05_spatial_validation_pipeline.R
│   ├── 06_ligand_receptor_pipeline.R
│   └── 07_target_visualization.R
├── scripts/
│   ├── run_daily_pipeline.py
│   ├── run_weekly_target_update.py
│   ├── initialize_project.py
│   └── check_disk_usage.py
├── notebooks/
│   ├── exploratory_bulk_analysis.qmd
│   ├── exploratory_scrna_analysis.qmd
│   └── exploratory_spatial_analysis.qmd
├── tests/
│   ├── test_paths.py
│   ├── test_schema.py
│   └── test_target_scoring.py
└── docs/
    ├── data_sources.md
    ├── analysis_strategy.md
    ├── target_score_definition.md
    └── operation_manual.md
```

注意：仓库代码可以放在 D 盘，也可以放在 GitHub；但所有大数据必须由路径函数写入 D 盘数据根目录。

---

## 3. 配置文件模板

### 3.1 `config/paths.yaml`

```yaml
data_root: "D:/Ovarian_AI_Target_Factory"
raw_dir: "D:/Ovarian_AI_Target_Factory/data_raw"
processed_dir: "D:/Ovarian_AI_Target_Factory/data_processed"
results_dir: "D:/Ovarian_AI_Target_Factory/results"
cache_dir: "D:/Ovarian_AI_Target_Factory/cache"
logs_dir: "D:/Ovarian_AI_Target_Factory/logs"

max_single_download_gb: 50
warn_if_c_drive_used: true
```

### 3.2 `config/search_terms.yaml`

```yaml
disease:
  - ovarian cancer
  - high-grade serous ovarian cancer
  - HGSOC
  - ovarian carcinoma
  - platinum resistant ovarian cancer
  - recurrent ovarian cancer

omics:
  - single-cell RNA-seq
  - spatial transcriptomics
  - proteogenomics
  - phosphoproteomics
  - multi-omics
  - methylation
  - copy number variation
  - digital pathology
  - radiomics

ai_methods:
  - artificial intelligence
  - machine learning
  - deep learning
  - foundation model
  - graph neural network
  - multimodal learning
  - perturbation prediction
  - virtual knockout
  - causal inference
  - target discovery

biology:
  - tumor microenvironment
  - macrophage
  - fibroblast
  - endothelial cell
  - hypoxia
  - CNV subclone
  - malignant subclone
  - ligand receptor
  - drug resistance
  - immune evasion
```

### 3.3 `config/target_scoring.yaml`

```yaml
score_max: 100

categories:
  disease_relevance:
    max: 15
    items:
      bulk_high_expression: 5
      multi_cohort_consistency: 5
      associated_with_stage_recurrence_resistance: 5

  clinical_value:
    max: 15
    items:
      os_or_pfs_association: 5
      multivariable_independence: 5
      predicts_platinum_parp_bev_response: 5

  multiomics_consistency:
    max: 15
    items:
      cnv_expression_support: 4
      methylation_expression_support: 3
      protein_support: 4
      phosphoprotein_or_pathway_support: 4

  single_cell_spatial:
    max: 20
    items:
      malignant_subclone_specificity: 5
      tme_interaction_support: 5
      spatial_colocalization_support: 5
      niche_or_invasive_front_specificity: 5

  functional_dependency:
    max: 15
    items:
      depmap_crispr_dependency: 5
      drug_sensitivity_association: 4
      virtual_ko_effect: 4
      actionable_pathway: 2

  novelty_publishability:
    max: 10
    items:
      underexplored_in_ovarian_cancer: 4
      clear_new_mechanistic_axis: 4
      translational_potential: 2

  experimental_feasibility:
    max: 10
    items:
      antibody_or_reagent_available: 3
      suitable_cell_line_expression: 3
      knockdown_or_overexpression_feasible: 2
      animal_organoid_or_coculture_feasible: 2

rank_thresholds:
  main_project: 80
  mechanism_validation: 65
  supplementary_candidate: 50
```

---

## 4. 数据源优先级

### 4.1 第一优先级：主干数据

```text
TCGA-OV / GDC：bulk RNA、CNV、甲基化、临床
cBioPortal：快速交叉验证
CPTAC-OV：蛋白组、磷酸化蛋白组
DepMap：CRISPR dependency、表达、CNV、药敏
GEO / SRA：bulk、scRNA、spatial 数据集
CELLxGENE / Single Cell Portal：标准化单细胞数据
HTAN：空间多模态肿瘤图谱
TCIA：病理图像、影像组学资源
```

### 4.2 数据集入库字段

所有数据集必须被整理成 `dataset_registry.tsv`：

```tsv
dataset_id	title	disease	histology	modality	platform	species	sample_count	cell_count	treatment_status	has_survival	has_platinum_response	has_spatial_coordinates	has_raw_count	has_image	download_url	paper_pmid	priority_score	status	notes
```

### 4.3 数据集优先级评分

```text
+3 卵巢癌 / HGSOC
+3 有治疗反应、铂耐药、PARP 耐药或复发信息
+2 有空间坐标
+2 有单细胞注释
+2 有配对 bulk / scRNA / spatial / pathology
+2 有生存信息
+1 有原始 count matrix
+1 有可复现代码或补充表格
-3 样本量太小且无验证价值
-3 只有 PDF 图，没有矩阵或 accession
-5 与卵巢癌关系弱且不可迁移
```

---

## 5. 每日自动化流水线

### 5.1 每日流程

```text
06:00 literature_watcher.py
06:20 dataset_watcher.py
06:40 update_dataset_registry.py
07:00 report_generator.py
07:10 输出 daily report
```

### 5.2 每日输出文件

```text
D:/Ovarian_AI_Target_Factory/results/daily_reports/YYYY-MM-DD/
├── literature_digest.json
├── literature_digest.md
├── new_dataset_registry.tsv
├── daily_evidence_report.md
├── codex_next_tasks.md
└── logs/
    └── daily_pipeline.log
```

### 5.3 每日报告结构

```markdown
# Daily Ovarian AI Target Report: YYYY-MM-DD

## 1. 今日新增高价值论文
- title
- journal/preprint server
- publication date
- modality
- available data/code
- relevance to ovarian cancer target discovery
- priority: high/medium/low

## 2. 今日新增数据集
- accession
- sample count
- modality
- download URL
- priority score
- recommended action

## 3. 今日值得学习的新策略
- 方法学名称
- 可迁移到卵巢癌的分析方式
- Codex 可执行任务

## 4. 候选靶点变化
- 新增候选
- 证据增强候选
- 证据减弱候选
- 建议淘汰候选

## 5. 需要 ChatGPT 判断的问题
- 哪个最像机制轴？
- 哪个最适合短期发文章？
- 哪个最适合基金？
- 哪个最适合湿实验？

## 6. 下一轮 Codex 任务
- script
- input
- output
- success criteria
```

---

## 6. 每周靶点更新流水线

### 6.1 每周流程

```text
周六：
1. 更新 TCGA-OV / bulk validation
2. 更新 DepMap dependency
3. 更新 scRNA 定位
4. 更新 spatial validation
5. 重新计算 target_score
6. 生成 Top 20 Target Cards

周日：
1. 将 weekly_evidence_report.md 交给 ChatGPT
2. ChatGPT 输出 Top 3 机制轴
3. ChatGPT 输出下一周 Codex 任务清单
```

### 6.2 每周输出文件

```text
D:/Ovarian_AI_Target_Factory/results/weekly_reports/YYYY-WW/
├── candidate_target_table.tsv
├── target_score_matrix.tsv
├── top20_target_cards.md
├── weekly_evidence_report.md
├── missing_evidence_table.tsv
├── reviewer_concern_table.tsv
└── next_week_codex_tasks.md
```

---

## 7. 候选靶点标准化证据表

Codex 必须输出 `candidate_target_table.tsv`：

```tsv
gene_symbol	target_score	rank_class	bulk_logfc	bulk_fdr	cox_hr	cox_p	cnv_cor	methylation_cor	protein_cor	phospho_signal	sc_main_celltype	malignant_subclone_specificity	spatial_niche	lr_axis	depmap_dependency	drug_sensitivity	virtual_ko_effect	novelty_score	experimental_feasibility	missing_evidence	reviewer_concerns	next_action
```

---

## 8. Target Card 模板

每个候选靶点生成一个 Markdown 卡片，保存到：

```text
D:/Ovarian_AI_Target_Factory/results/target_cards/<GENE>.md
```

模板：

```markdown
# Target Card: <GENE>

## 1. Basic information
- Gene symbol:
- Gene type:
- Location:
- Druggability:
- Antibody/reagent availability:

## 2. Bulk evidence
- TCGA-OV expression:
- External GEO validation:
- OS/PFS association:
- Platinum/PARP/bevacizumab relevance:

## 3. Multi-omics evidence
- CNV-expression association:
- Methylation-expression association:
- Protein evidence:
- Phosphoprotein/pathway evidence:

## 4. Single-cell evidence
- Main expressing cell type:
- Malignant subclone specificity:
- Associated tumor state:
- Associated TME state:

## 5. Spatial evidence
- Spatial niche:
- Neighboring cells:
- Invasive front / hypoxia / necrosis / vascular association:
- Spatial ligand-receptor evidence:

## 6. Functional evidence
- DepMap CRISPR dependency:
- Drug sensitivity association:
- Virtual knockout effect:

## 7. Mechanistic hypothesis
- Upstream driver:
- Target gene:
- Downstream pathway:
- Phenotype:
- Candidate mechanism axis:

## 8. Weakness and reviewer concerns
- Missing evidence:
- Potential confounders:
- Reviewer concern 1:
- Reviewer concern 2:
- Reviewer concern 3:

## 9. Next Codex tasks
- Analysis task 1:
- Analysis task 2:
- Figure task:
- Validation dataset:

## 10. Minimal wet-lab validation
- Cell lines:
- Perturbation:
- Assays:
- Rescue experiment:
```

---

## 9. 首批 ChatGPT Prompts

以下 prompts 保存到 `prompts/` 目录。

### 9.1 `prompts/01_paper_summarizer.md`

```markdown
你现在是肿瘤多组学 PI、Nature Cancer 审稿人和卵巢癌生信专家。
请阅读我提供的论文元数据、摘要、图表说明和可用数据链接。

任务：
1. 判断这篇论文是否对“卵巢癌多组学/多模态靶点发现”有价值；
2. 将论文分类为：
   - 直接提供卵巢癌数据集
   - 提供可迁移的 AI/多组学方法
   - 提供机制轴启发
   - 提供药物/靶点启发
   - 低优先级
3. 提取可复用策略；
4. 提取可下载数据集 accession、代码地址、补充表格；
5. 给出是否值得 Codex 下载和复现；
6. 如果值得复现，请生成 Codex 可执行任务。

输出格式：
- Paper summary
- Relevance score: 0-10
- Reusable strategy
- Data/code availability
- Candidate genes/pathways
- Suggested Codex tasks
- Reviewer-level comments
```

### 9.2 `prompts/02_dataset_extractor.md`

```markdown
你现在是公共数据库数据挖掘专家。
请阅读我提供的数据集页面、摘要、样本信息和下载链接。

任务：
1. 判断该数据集是否适合卵巢癌靶点发现；
2. 提取 dataset_id、modality、platform、sample_count、cell_count、treatment_status、是否有生存信息、是否有空间坐标、是否有原始 count；
3. 判断是否适合：
   - bulk validation
   - scRNA validation
   - spatial validation
   - drug resistance analysis
   - ligand-receptor analysis
   - virtual knockout analysis
4. 给出 priority_score；
5. 生成 Codex 下载和预处理任务。

输出为 Markdown + TSV 两部分。
```

### 9.3 `prompts/03_target_reviewer.md`

```markdown
你现在同时扮演三个角色：
1. 肿瘤多组学 PI；
2. Nature Cancer / Cancer Cell 审稿人；
3. 临床转化导向的妇瘤医生科学家。

请阅读 candidate_target_table.tsv 和 target cards。

任务：
1. 从候选靶点中选出最值得推进的 3 个；
2. 判断每个靶点属于：
   - tumor-intrinsic driver
   - TME communication target
   - resistance-associated state marker
   - immune evasion regulator
   - synthetic lethal target
3. 指出每个靶点当前证据链缺口；
4. 设计下一轮 Codex 可执行分析任务；
5. 预测审稿人会如何质疑；
6. 给出最小湿实验验证方案；
7. 判断是否可以形成新机制轴和文章故事线。

输出：
- Top 3 targets
- Recommended mechanism axis
- Evidence strengths
- Evidence gaps
- Reviewer concerns
- Next Codex tasks
- Minimal wet-lab validation
```

### 9.4 `prompts/04_codex_task_generator.md`

```markdown
你是资深生信工程师和科研项目经理。
请根据 ChatGPT 生成的分析建议，把每个建议拆解为 Codex 可执行任务。

每个任务必须包含：
1. 任务名称；
2. 背景目的；
3. 输入文件；
4. 输出文件；
5. 推荐脚本路径；
6. 关键函数；
7. 成功标准；
8. 失败时的排错策略；
9. 是否涉及大文件下载；
10. 若涉及大文件，必须写入 D:/Ovarian_AI_Target_Factory，不得写入 C 盘。

输出格式为 Markdown checklist。
```

### 9.5 `prompts/05_reviewer_critique.md`

```markdown
你现在是严厉的 Cancer Cell / Nature Cancer 审稿人。
请审查这个候选靶点和机制轴。

请重点质疑：
1. 是否只是相关性，而不是因果性；
2. 是否只是 cell state marker，而不是 driver；
3. 是否受肿瘤纯度、批次效应、细胞组成影响；
4. 是否有蛋白层面证据；
5. 是否有空间邻近性证据；
6. 是否有功能扰动证据；
7. 是否有临床转化意义；
8. 是否在卵巢癌中足够新颖；
9. 需要补哪些图才能让文章更强。

输出：
- Major concerns
- Minor concerns
- Required analyses
- Required wet-lab experiments
- Decision: reject / major revision / promising
```

### 9.6 `prompts/06_wetlab_validation_designer.md`

```markdown
你现在是妇瘤基础实验 PI。
请基于候选靶点证据链设计最小湿实验验证方案。

要求：
1. 只设计资源可控、适合临床医生协作完成的实验；
2. 优先选择细胞系、共培养、siRNA/shRNA、阻断抗体、qPCR/WB/IF/Transwell/CCK8；
3. 必须包含 rescue 或 pathway inhibitor 以增强因果性；
4. 给出每组实验的目的、分组、读出指标、预期结果和替代方案；
5. 区分短期可完成实验和长期增强实验。

输出：
- Minimal validation package
- Mechanistic validation package
- Translational validation package
- Expected figures
```

---

## 10. 首批 Python 脚本任务清单

### 10.1 `scripts/initialize_project.py`

目的：初始化目录，尤其是在 D 盘创建数据目录。

输入：无。

输出：目录结构、默认配置文件。

成功标准：

```text
D:/Ovarian_AI_Target_Factory/data_raw 存在
D:/Ovarian_AI_Target_Factory/data_processed 存在
D:/Ovarian_AI_Target_Factory/results 存在
D:/Ovarian_AI_Target_Factory/cache 存在
D:/Ovarian_AI_Target_Factory/logs 存在
```

Codex 要求：

```text
- 使用 pathlib
- 检测 C 盘使用风险
- 如果 D 盘不存在，询问或警告，但仍允许 fallback
- 不下载任何大文件
```

### 10.2 `src/ovarian_ai/literature/literature_watcher.py`

目的：每日检索最新论文。

数据源：

```text
PubMed / Europe PMC / bioRxiv / medRxiv / arXiv / journal RSS
```

输入：

```text
config/search_terms.yaml
config/journals.yaml
```

输出：

```text
results/daily_reports/YYYY-MM-DD/literature_digest.json
results/daily_reports/YYYY-MM-DD/literature_digest.md
```

核心字段：

```json
{
  "title": "",
  "authors": [],
  "journal": "",
  "date": "",
  "doi": "",
  "pmid": "",
  "abstract": "",
  "url": "",
  "modality": [],
  "disease": [],
  "method_tags": [],
  "data_availability": "",
  "code_availability": "",
  "priority_score": 0,
  "reason": ""
}
```

### 10.3 `src/ovarian_ai/datasets/dataset_watcher.py`

目的：每日检索新数据集。

数据源：

```text
GEO / SRA / ArrayExpress / ENA / CELLxGENE / Single Cell Portal / HTAN / TCIA / ProteomeXchange / DepMap / Zenodo / Figshare / GitHub
```

输出：

```text
results/daily_reports/YYYY-MM-DD/new_dataset_registry.tsv
```

成功标准：至少输出以下字段：

```text
dataset_id, title, disease, modality, platform, sample_count, download_url, priority_score, recommended_action
```

### 10.4 `src/ovarian_ai/depmap/depmap_pipeline.py`

目的：读取 DepMap 数据，评估候选基因在卵巢癌细胞系中的功能依赖。

输入：

```text
D:/Ovarian_AI_Target_Factory/data_raw/depmap/
candidate_gene_list.txt
```

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/depmap/depmap_ovarian_dependency.tsv
D:/Ovarian_AI_Target_Factory/results/figures/depmap_dependency_heatmap.pdf
```

分析内容：

```text
- 筛选 ovarian cancer cell lines
- 提取 CRISPR gene effect
- 提取 expression
- 提取 copy number
- 如有可用药敏数据，关联 drug sensitivity
- 输出每个基因的 dependency summary
```

### 10.5 `src/ovarian_ai/scoring/target_scoring.py`

目的：汇总多证据并计算靶点评分。

输入：

```text
bulk_result.tsv
cnv_result.tsv
methylation_result.tsv
cptac_result.tsv
scrna_result.tsv
spatial_result.tsv
depmap_result.tsv
virtual_ko_result.tsv
config/target_scoring.yaml
```

输出：

```text
D:/Ovarian_AI_Target_Factory/results/weekly_reports/YYYY-WW/candidate_target_table.tsv
D:/Ovarian_AI_Target_Factory/results/weekly_reports/YYYY-WW/target_score_matrix.tsv
```

要求：

```text
- 缺失证据不能当作 0 分直接否定，而是标记为 missing
- 输出 missing_evidence 字段
- 输出 reviewer_concerns 字段
- 输出 next_action 字段
```

### 10.6 `src/ovarian_ai/scoring/target_card.py`

目的：为每个候选靶点生成 Target Card。

输入：

```text
candidate_target_table.tsv
各证据结果表
```

输出：

```text
D:/Ovarian_AI_Target_Factory/results/target_cards/<GENE>.md
```

### 10.7 `src/ovarian_ai/report/report_generator.py`

目的：生成每日和每周报告。

输入：

```text
literature_digest.json
new_dataset_registry.tsv
candidate_target_table.tsv
target_cards/
```

输出：

```text
D:/Ovarian_AI_Target_Factory/results/daily_reports/YYYY-MM-DD/daily_evidence_report.md
D:/Ovarian_AI_Target_Factory/results/weekly_reports/YYYY-WW/weekly_evidence_report.md
```

### 10.8 `src/ovarian_ai/virtual_ko/virtual_ko_pipeline.py`

目的：对候选基因进行虚拟敲除或扰动预测。

第一版可以先做轻量级实现，不强求复杂深度学习模型：

```text
- 对候选基因 high vs low 细胞比较 malignant score、hypoxia、EMT、KRAS、stemness、drug resistance score
- 构建 gene set score change 作为 proxy virtual KO
- 后续再接入 CellOracle、scGen、CPA、scVI-tools 或自建 GNN
```

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/virtual_ko/virtual_ko_summary.tsv
```

### 10.9 `scripts/check_disk_usage.py`

目的：防止 C 盘被大数据撑爆。

要求：

```text
- 检查 D:/Ovarian_AI_Target_Factory 总占用
- 检查 C 盘剩余空间
- 如果脚本检测到 data_raw 或 cache 在 C 盘，立即警告
- 输出 logs/disk_usage_YYYY-MM-DD.log
```

### 10.10 `scripts/run_daily_pipeline.py`

目的：串联每日任务。

执行顺序：

```text
1. initialize_project.py
2. check_disk_usage.py
3. literature_watcher.py
4. dataset_watcher.py
5. report_generator.py --mode daily
```

---

## 11. 首批 R 脚本任务清单

### 11.1 `R/01_tcga_ov_pipeline.R`

目的：建立 TCGA-OV 主干分析。

输入：

```text
TCGA-OV RNA-seq
TCGA-OV clinical
TCGA-OV CNV
TCGA-OV methylation
候选基因列表
```

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/tcga_ov/tcga_expression_summary.tsv
D:/Ovarian_AI_Target_Factory/data_processed/tcga_ov/tcga_survival_summary.tsv
D:/Ovarian_AI_Target_Factory/data_processed/tcga_ov/tcga_cnv_expression_summary.tsv
D:/Ovarian_AI_Target_Factory/data_processed/tcga_ov/tcga_methylation_expression_summary.tsv
```

分析：

```text
- 肿瘤 vs 正常表达差异，如果无正常，则使用外部正常卵巢/输卵管数据
- Cox regression
- Kaplan-Meier
- timeROC，如果样本量允许
- CNV-expression correlation
- methylation-expression correlation
```

### 11.2 `R/02_bulk_validation_pipeline.R`

目的：在 GEO bulk 队列中验证候选靶点。

输入：

```text
GEO 表达矩阵
表型文件
候选基因列表
```

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/bulk_validation/bulk_validation_summary.tsv
```

分析：

```text
- 多队列表达一致性
- 复发/耐药/预后相关性
- meta-analysis effect size
- batch-aware visualization
```

### 11.3 `R/03_cptac_ov_pipeline.R`

目的：整合 CPTAC 卵巢癌蛋白组和磷酸化证据。

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/cptac_ov/cptac_protein_summary.tsv
D:/Ovarian_AI_Target_Factory/data_processed/cptac_ov/cptac_phospho_summary.tsv
```

分析：

```text
- RNA-protein consistency
- protein-survival association，如临床数据允许
- pathway/phosphosite-level evidence
```

### 11.4 `R/04_scrna_validation_pipeline.R`

目的：单细胞定位和恶性亚克隆验证。

输入：

```text
scRNA count matrix / Seurat object
metadata
候选基因列表
```

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/scrna/scrna_target_summary.tsv
D:/Ovarian_AI_Target_Factory/results/figures/scrna_featureplots/
D:/Ovarian_AI_Target_Factory/results/figures/scrna_dotplots/
```

分析：

```text
- QC
- normalization
- clustering
- cell type annotation
- malignant epithelial identification
- inferCNV 或 copyKAT 识别 malignant subclone
- module scores: hypoxia, EMT, KRAS, stemness, proliferation, immune evasion, drug resistance
- 候选基因与 malignant state 的相关性
```

### 11.5 `R/05_spatial_validation_pipeline.R`

目的：空间转录组验证。

输入：

```text
Visium/GeoMx/ST 表达矩阵
空间坐标
候选基因列表
可选 scRNA reference
```

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/spatial/spatial_target_summary.tsv
D:/Ovarian_AI_Target_Factory/results/figures/spatial/
```

分析：

```text
- spatial clustering
- target spatial expression
- tumor/TME deconvolution
- macrophage/CAF/endothelial proximity
- hypoxia/invasive front/necrosis niche association
- ligand-receptor spatial colocalization
```

### 11.6 `R/06_ligand_receptor_pipeline.R`

目的：细胞通讯和机制轴筛选。

输入：

```text
Seurat object
cell type annotation
候选 ligand/receptor 列表
```

输出：

```text
D:/Ovarian_AI_Target_Factory/data_processed/ligand_receptor/lr_axis_summary.tsv
D:/Ovarian_AI_Target_Factory/results/figures/ligand_receptor/
```

分析：

```text
- LIANA / CellChat / NicheNet 至少实现一种
- macrophage/CAF/endothelial → malignant subclone
- receptor downstream pathway score
- 空间邻近性整合
```

### 11.7 `R/07_target_visualization.R`

目的：为候选靶点生成标准化图件。

必须支持图件：

```text
1. 多组学证据热图
2. target score barplot
3. bulk survival forest plot
4. scRNA dotplot / featureplot
5. spatial feature map
6. ligand-receptor chord / bubble plot
7. virtual KO effect plot
8. target evidence radar plot
```

输出：

```text
D:/Ovarian_AI_Target_Factory/results/figures/<GENE>/
```

---

## 12. Codex 第一阶段执行顺序

第一阶段目标：4 周内跑通最小可行版本，不追求一次性完成所有高级模块。

### Week 1：项目骨架 + 文献/数据雷达

```text
1. 创建目录结构
2. 实现 D 盘路径管理
3. 实现 initialize_project.py
4. 实现 check_disk_usage.py
5. 实现 literature_watcher.py 第一版
6. 实现 dataset_watcher.py 第一版
7. 生成 daily report 第一版
```

### Week 2：TCGA-OV + bulk validation

```text
1. 实现 TCGA-OV RNA/clinical/CNV/methylation 读取
2. 实现候选基因表达、生存、CNV、甲基化分析
3. 接入 1-2 个 GEO bulk 队列
4. 输出初版 candidate_target_table.tsv
```

### Week 3：DepMap + scRNA

```text
1. 接入 DepMap CRISPR dependency
2. 筛选 ovarian cancer cell lines
3. 接入 1-2 个公开卵巢癌 scRNA 数据集
4. 完成 cell type specificity 和 malignant state 评分
5. 更新 target_score
```

### Week 4：spatial + target cards

```text
1. 接入 1 个空间转录组数据集
2. 做 target spatial expression 和邻近性分析
3. 生成 Target Cards
4. 生成 weekly_evidence_report.md
5. 交给 ChatGPT 进行 Top 3 机制轴评审
```

---

## 13. 给 Codex 的总启动 Prompt

请把以下内容作为第一条 Codex 指令：

```markdown
你是一个资深生信工程师、Python/R 开发者和科研项目架构师。

请根据当前项目需求，创建一个名为 ovarian_ai_target_factory 的项目，用于自动化发现卵巢癌多组学/多模态候选靶点。

强制要求：
1. 所有大数据、缓存、中间文件和结果默认写入 D:/Ovarian_AI_Target_Factory；
2. 不得默认写入 C 盘 Downloads、Documents、AppData 或系统临时目录；
3. 路径必须通过统一函数读取：Python 用 src/ovarian_ai/utils/paths.py，R 用 R/utils_paths.R；
4. 如果 D 盘不存在，允许 fallback 到 ./local_data，但必须发出明显警告；
5. 所有脚本都必须有命令行参数、日志输出、错误处理和 dry-run 模式；
6. 所有下载脚本必须支持断点续传或至少检测文件是否已存在，避免重复下载；
7. 每个模块必须输出标准化 TSV/JSON/Markdown，方便 ChatGPT 读取；
8. 先完成最小可行版本，不要一开始实现复杂深度学习模型。

请按以下顺序执行：
1. 创建项目目录结构；
2. 创建 config/paths.yaml、config/search_terms.yaml、config/target_scoring.yaml；
3. 实现 Python 路径工具；
4. 实现 R 路径工具；
5. 实现 initialize_project.py；
6. 实现 check_disk_usage.py；
7. 实现 literature_watcher.py 第一版；
8. 实现 dataset_watcher.py 第一版；
9. 实现 report_generator.py 第一版；
10. 写 README.md，说明如何在 Windows 和 WSL 下运行。

每完成一个模块，请运行最小测试，并在 results/logs/ 中保存日志。
```

---

## 14. Makefile 建议

```makefile
init:
	python scripts/initialize_project.py

check-disk:
	python scripts/check_disk_usage.py

daily:
	python scripts/run_daily_pipeline.py

weekly:
	python scripts/run_weekly_target_update.py

tcga:
	Rscript R/01_tcga_ov_pipeline.R

depmap:
	python -m ovarian_ai.depmap.depmap_pipeline

score:
	python -m ovarian_ai.scoring.target_scoring

report:
	python -m ovarian_ai.report.report_generator --mode weekly
```

---

## 15. `.gitignore` 必须包含

```gitignore
# large data
/data_raw/
/data_processed/
/cache/
/results/figures/
*.h5ad
*.h5
*.loom
*.rds
*.RDS
*.bam
*.fastq
*.fastq.gz
*.fq.gz
*.tar
*.tar.gz
*.zip
*.7z

# local fallback data
/local_data/

# logs
/logs/
*.log

# secrets
.env
config/secrets.yaml

# OS / IDE
.DS_Store
Thumbs.db
.vscode/
.Rproj.user/
```

注意：如果代码仓库在 GitHub，大数据不要提交到 Git。

---

## 16. 质量控制与失败处理

每个脚本必须满足：

```text
1. 支持 --dry-run
2. 支持 --config config/paths.yaml
3. 支持 --outdir 参数，但默认仍在 D 盘根目录下
4. 运行前检查磁盘空间
5. 大文件下载前估计大小或提示未知大小
6. 文件存在时跳过，除非 --force
7. 输出日志
8. 输出可供 ChatGPT 阅读的 Markdown 摘要
```

推荐命令行接口示例：

```bash
python scripts/run_daily_pipeline.py --config config/paths.yaml --dry-run
python scripts/run_daily_pipeline.py --config config/paths.yaml
Rscript R/01_tcga_ov_pipeline.R --config config/paths.yaml --candidate candidate_gene_list.txt
```

---

## 17. 最小可行版本验收标准

MVP 完成后，应能得到：

```text
1. D:/Ovarian_AI_Target_Factory 目录已建立
2. 每日文献报告可生成
3. 每日数据集报告可生成
4. TCGA-OV 至少完成表达 + 生存 + CNV 分析
5. DepMap 至少完成 ovarian cancer cell line dependency 分析
6. 至少 1 个 scRNA 数据集完成靶点定位分析
7. 至少 1 个 spatial 数据集完成空间表达分析
8. candidate_target_table.tsv 可生成
9. 至少 10 个 Target Cards 可生成
10. weekly_evidence_report.md 可直接交给 ChatGPT 评审
```

---

## 18. 医生本人每周只需要看的内容

```text
1. weekly_evidence_report.md
2. Top 20 Target Cards
3. candidate_target_table.tsv
4. reviewer_concern_table.tsv
5. next_week_codex_tasks.md
```

你本人每周只做三个判断：

```text
1. 这个靶点是否有真实临床意义？
2. 这个机制是否能讲成一个清晰故事？
3. 这个方向是否适合当前资源做最小实验验证？
```

---

## 19. 推荐第一批候选方向，但不写死靶点

第一版系统不应该预设某一个靶点，而应优先筛选以下类型：

```text
1. CNV-high malignant subclone 特异 receptor / TF / metabolic gene
2. macrophage / CAF / endothelial → malignant subclone ligand-receptor 轴
3. 铂耐药、PARP 耐药或复发相关 state driver
4. RNA-protein-phospho 一致的 kinase/receptor/surface protein
5. 空间侵袭前沿、缺氧生态位、坏死边缘相关靶点
6. DepMap 显示卵巢癌细胞系依赖的功能基因
```

---

## 20. 最终产出形态

本项目最终会不断产出：

```text
1. 每日文献/数据报告
2. 每周候选靶点评分表
3. 标准化 Target Cards
4. 可发表机制轴候选
5. Codex 下一轮任务清单
6. 可直接用于文章/基金的图件和分析报告
```

本项目的核心价值是：

```text
临床问题判断
+ 肿瘤生物学逻辑
+ 公共数据库规模化整合
+ AI 自动化代码执行
+ 多模态证据评分
+ 可验证机制轴输出
```

这套系统能最大化利用医生碎片时间，把重复性检索、下载、整理、跑代码和初筛工作交给 Codex，把机制判断和课题设计交给 ChatGPT，把最终临床价值判断留给你本人。
