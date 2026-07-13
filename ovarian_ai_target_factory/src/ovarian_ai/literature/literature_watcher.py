from __future__ import annotations

import argparse
import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import yaml

from ovarian_ai.utils.paths import assert_not_c_data_path, daily_reports_root


NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EXCLUDE_ARTICLE_TERMS = (
    "corrigendum",
    "erratum",
    "correction",
    "retraction",
    "editorial",
    "letter",
    "comment",
    "author correction",
    "publisher correction",
    "expression of concern",
)
PROGNOSTIC_TERMS = ("prognostic", "prognosis", "signature", "nomogram", "cox", "lasso")
NONCODING_TERMS = ("mirna", "microrna", "lncrna", "circrna", "non-coding", "noncoding")
VALIDATION_TERMS = (
    "public dataset",
    "github",
    "zenodo",
    "figshare",
    "single-cell",
    "single cell",
    "spatial",
    "proteomics",
    "functional validation",
    "drug response",
    "crispr",
    "depmap",
    "mechanistic",
    "experiment",
    "external validation",
)
UPGRADE_TERMS = (
    "hgsoc",
    "high-grade serous ovarian",
    "single-cell",
    "single cell",
    "spatial transcriptomics",
    "spatial proteomics",
    "proteogenomics",
    "phosphoproteomics",
    "cnv",
    "subclone",
    "clonal evolution",
    "tumor microenvironment",
    "macrophage",
    "caf",
    "t cell",
    "b cell",
    "endothelial",
    "platinum resistance",
    "parp inhibitor",
    "bevacizumab",
    "depmap",
    "crispr",
    "drug sensitivity",
    "functional dependency",
    "gse",
    "github",
    "zenodo",
    "figshare",
    "ligand-receptor",
    "therapeutic vulnerability",
)


def yyyymmdd(value: str) -> str:
    return value.replace("-", "")


def setup_logger(outdir: Path, run_date: str) -> logging.Logger:
    logger = logging.getLogger("literature_watcher")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(outdir / "logs" / f"literature_watcher_{yyyymmdd(run_date)}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def read_search_terms(config_path: Path) -> dict:
    path = config_path.parent / "search_terms.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_pubmed_query(terms: dict) -> str:
    disease_terms = terms.get("disease") or ["ovarian cancer"]
    method_terms = (terms.get("omics") or []) + (terms.get("ai_methods") or []) + (terms.get("biology") or [])
    disease_query = " OR ".join(f'"{term}"[Title/Abstract]' for term in disease_terms[:6])
    method_query = " OR ".join(f'"{term}"[Title/Abstract]' for term in method_terms[:14])
    if method_query:
        return f"({disease_query}) AND ({method_query})"
    return f"({disease_query})"


def fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "OvarianAITargetFactory/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def pubmed_search(query: str, retmax: int, logger: logging.Logger) -> list[str]:
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": str(retmax),
            "sort": "pub date",
        }
    )
    url = f"{NCBI_BASE}/esearch.fcgi?{params}"
    try:
        payload = json.loads(fetch_text(url))
        return payload.get("esearchresult", {}).get("idlist", [])
    except Exception as exc:
        logger.exception("PubMed esearch failed: %s", exc)
        return []


def text_or_empty(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return re.sub(r"\s+", " ", node.text).strip()


def article_date(article: ET.Element) -> str:
    pub_date = article.find(".//JournalIssue/PubDate")
    if pub_date is None:
        return ""
    year = text_or_empty(pub_date.find("Year"))
    month = text_or_empty(pub_date.find("Month"))
    day = text_or_empty(pub_date.find("Day"))
    return "-".join(part for part in (year, month, day) if part)


def publication_types(article: ET.Element) -> list[str]:
    return [text_or_empty(node) for node in article.findall(".//PublicationType") if text_or_empty(node)]


def infer_tags(text: str, candidates: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in candidates if term.lower() in lowered]


def priority_from_tags(modality: list[str], method_tags: list[str], disease: list[str]) -> tuple[int, str]:
    score = 30 + min(len(modality) * 8, 24) + min(len(method_tags) * 5, 25) + min(len(disease) * 6, 18)
    score = min(score, 100)
    if score >= 70:
        return score, "high"
    if score >= 50:
        return score, "medium"
    return score, "low"


def detect_availability(text: str, kind: str) -> str:
    lowered = text.lower()
    if kind == "data" and any(token in lowered for token in ("gse", "geo", "sra", "arrayexpress", "zenodo", "figshare", "tcga")):
        return "Likely public data/accession mentioned in metadata"
    if kind == "code" and any(token in lowered for token in ("github", "gitlab", "code availability", "source code")):
        return "Likely public code mentioned in metadata"
    return "Unknown from PubMed metadata"


def score_specificity(text: str) -> int:
    lowered = text.lower()
    score = 0
    if any(token in lowered for token in ("ovarian cancer", "ovarian carcinoma", "hgsoc", "high-grade serous ovarian")):
        score += 45
    if any(token in lowered for token in ("sample", "cohort", "patient", "cell line", "tumor", "tumour")):
        score += 25
    if any(token in lowered for token in ("primary tumor", "platinum", "parp", "recurrent", "resistance")):
        score += 20
    return min(score, 100)


def score_omics(text: str) -> int:
    lowered = text.lower()
    score = 0
    for token in ("single-cell", "single cell", "spatial", "proteogenomics", "phosphoproteomics", "cnv", "methylation", "crispr", "depmap"):
        if token in lowered:
            score += 15
    return min(score, 100)


def score_translational(text: str) -> int:
    lowered = text.lower()
    score = 0
    for token in ("target", "pathway", "therapy", "drug", "resistance", "vulnerability", "ligand-receptor", "functional", "mechanistic"):
        if token in lowered:
            score += 12
    return min(score, 100)


def score_to_priority(score: int, status: str) -> str:
    if status == "exclude":
        return "exclude"
    if status == "needs_manual_review":
        return "needs_manual_review"
    if score >= 80:
        return "high"
    if score >= 65:
        return "medium-high"
    if score >= 50:
        return "medium"
    if score >= 35:
        return "medium-low"
    return "low"


def refine_literature_record(record: dict) -> dict:
    title = record.get("title", "")
    abstract = record.get("abstract", "")
    article_types = record.get("article_type", [])
    text = f"{title} {abstract} {' '.join(article_types)}"
    lowered = text.lower()
    title_lower = title.lower()

    evidence_tags = [term for term in UPGRADE_TERMS if term in lowered]
    disease_score = score_specificity(text)
    omics_score = score_omics(text)
    translational_score = score_translational(text)
    final_score = int(round(disease_score * 0.35 + omics_score * 0.3 + translational_score * 0.25 + min(len(evidence_tags) * 5, 10)))

    exclusion_status = "keep"
    exclusion_reason = ""
    downgrade_reason = ""
    false_positive_reason = ""

    if any(term in title_lower for term in EXCLUDE_ARTICLE_TERMS) or any(
        any(term in article_type.lower() for term in EXCLUDE_ARTICLE_TERMS) for article_type in article_types
    ):
        exclusion_status = "exclude"
        exclusion_reason = "non-original article type"
    elif "ovarian" not in lowered or disease_score < 45:
        exclusion_status = "exclude"
        false_positive_reason = "keyword hit without ovarian-cancer-specific biological or clinical context"
        final_score = min(final_score, 20)
    elif not abstract.strip():
        exclusion_status = "needs_manual_review"
        downgrade_reason = "insufficient metadata"
        final_score = min(final_score, 45)
    elif any(term in lowered for term in PROGNOSTIC_TERMS) and not any(term in lowered for term in VALIDATION_TERMS):
        exclusion_status = "downgrade"
        downgrade_reason = "prognostic model only; lacks public code/data or mechanistic/multimodal validation"
        final_score = min(final_score, 40)
    elif any(term in lowered for term in NONCODING_TERMS) and not any(term in lowered for term in ("mechanistic", "functional", "spatial", "single-cell", "single cell", "proteomics", "experiment")):
        exclusion_status = "downgrade"
        downgrade_reason = "non-coding RNA signature without strong mechanistic or multimodal validation"
        final_score = min(final_score, 40)
    elif "pan-cancer" in lowered and not any(term in lowered for term in ("ovarian cohort", "ovarian-specific", "hgsoc", "ovarian cancer mechanism")):
        exclusion_status = "downgrade"
        downgrade_reason = "pan-cancer analysis without ovarian-cancer-specific evidence"
        final_score = min(final_score, 45)
    elif all(term in lowered for term in ("cox", "lasso")) and "nomogram" in lowered and not any(term in lowered for term in ("external validation", "github", "experiment", "mechanistic")):
        exclusion_status = "downgrade"
        downgrade_reason = "routine bioinformatics signature without strong validation"
        final_score = min(final_score, 40)

    refined = dict(record)
    refined.update(
        {
            "exclusion_status": exclusion_status,
            "exclusion_reason": exclusion_reason,
            "downgrade_reason": downgrade_reason,
            "false_positive_reason": false_positive_reason,
            "evidence_tags": evidence_tags,
            "data_availability": detect_availability(text, "data"),
            "code_availability": detect_availability(text, "code"),
            "disease_specificity_score": disease_score,
            "omics_relevance_score": omics_score,
            "translational_relevance_score": translational_score,
            "final_literature_score": final_score,
            "priority": score_to_priority(final_score, exclusion_status),
        }
    )
    return refined


def write_filtering_audit(records: list[dict], path: Path, run_date: str) -> None:
    def section(title: str, selected: list[dict]) -> list[str]:
        lines = [f"## {title}"]
        if not selected:
            return lines + ["- None", ""]
        for item in selected:
            lines.extend(
                [
                    f"- {item.get('title', '(untitled)')}",
                    f"  - PMID: {item.get('pmid', '')}",
                    f"  - priority: {item.get('priority', '')}",
                    f"  - exclusion_status: {item.get('exclusion_status', '')}",
                    f"  - exclusion_reason: {item.get('exclusion_reason', '')}",
                    f"  - downgrade_reason: {item.get('downgrade_reason', '')}",
                    f"  - false_positive_reason: {item.get('false_positive_reason', '')}",
                ]
            )
        return lines + [""]

    excluded = [item for item in records if item.get("exclusion_status") == "exclude"]
    downgraded = [item for item in records if item.get("exclusion_status") == "downgrade"]
    false_positive = [item for item in records if item.get("false_positive_reason")]
    retained = [item for item in records if item.get("priority") in {"high", "medium-high"}]
    lines = [f"# Literature Filtering Audit: {run_date}", ""]
    lines += section("Excluded articles", excluded)
    lines += section("Downgraded articles", downgraded)
    lines += section("False positive articles", false_positive)
    lines += section("Retained high / medium-high articles", retained)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_pubmed_records(xml_text: str, terms: dict, logger: logging.Logger) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except Exception as exc:
        logger.exception("PubMed efetch XML parse failed: %s", exc)
        return []

    omics = terms.get("omics") or []
    methods = (terms.get("ai_methods") or []) + (terms.get("biology") or [])
    diseases = terms.get("disease") or []
    records = []
    for article in root.findall(".//PubmedArticle"):
        citation = article.find(".//MedlineCitation")
        pmid = text_or_empty(citation.find("PMID") if citation is not None else None)
        title = text_or_empty(article.find(".//ArticleTitle"))
        abstract = " ".join(text_or_empty(node) for node in article.findall(".//AbstractText")).strip()
        journal = text_or_empty(article.find(".//Journal/Title"))
        authors = []
        for author in article.findall(".//Author")[:8]:
            last = text_or_empty(author.find("LastName"))
            fore = text_or_empty(author.find("ForeName"))
            collective = text_or_empty(author.find("CollectiveName"))
            name = collective or " ".join(part for part in (fore, last) if part)
            if name:
                authors.append(name)
        doi = ""
        for article_id in article.findall(".//ArticleId"):
            if article_id.attrib.get("IdType") == "doi":
                doi = text_or_empty(article_id)
                break
        searchable = f"{title} {abstract}"
        modality = infer_tags(searchable, omics)
        method_tags = infer_tags(searchable, methods)
        disease = infer_tags(searchable, diseases)
        priority_score, priority = priority_from_tags(modality, method_tags, disease)
        article_types = publication_types(article)
        records.append(
            {
                "title": title,
                "authors": authors,
                "journal": journal,
                "date": article_date(article),
                "article_type": article_types,
                "doi": doi,
                "pmid": pmid,
                "abstract": abstract,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "modality": modality,
                "disease": disease,
                "method_tags": method_tags,
                "data_availability": "Unknown from PubMed metadata",
                "code_availability": "Unknown from PubMed metadata",
                "priority_score": priority_score,
                "priority": priority,
                "reason": "Matched ovarian cancer terms and at least one configured omics/AI/biology search concept.",
            }
        )
    return records


def fetch_pubmed_records(query: str, retmax: int, terms: dict, logger: logging.Logger) -> list[dict]:
    pmids = pubmed_search(query, retmax, logger)
    if not pmids:
        return []
    params = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
    url = f"{NCBI_BASE}/efetch.fcgi?{params}"
    try:
        return parse_pubmed_records(fetch_text(url), terms, logger)
    except Exception as exc:
        logger.exception("PubMed efetch failed: %s", exc)
        return []


def write_markdown(records: list[dict], path: Path, run_date: str) -> None:
    lines = [f"# Literature Digest: {run_date}", ""]
    for item in records:
        lines.extend(
            [
                f"## {item['title']}",
                f"- Source: {item['journal']}",
                f"- Date: {item['date']}",
                f"- Modality: {', '.join(item['modality'])}",
                f"- Priority: {item['priority']} ({item['priority_score']})",
                f"- Data/code: {item['data_availability']} / {item['code_availability']}",
                f"- Relevance: {item['reason']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    run_date: str | None = None,
    config: Path | None = None,
    outdir: Path | None = None,
    dry_run: bool = False,
    retmax: int = 20,
) -> Path:
    selected_date = run_date or date.today().isoformat()
    report_dir = outdir or daily_reports_root(config)
    assert_not_c_data_path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "logs").mkdir(parents=True, exist_ok=True)
    logger = setup_logger(report_dir, selected_date)
    config_path = config or Path("config/paths.yaml")
    terms = read_search_terms(config_path)
    query = build_pubmed_query(terms)

    logger.info("Starting PubMed literature search with retmax=%s", retmax)
    logger.info("PubMed query: %s", query)
    records = [] if dry_run else fetch_pubmed_records(query, retmax, terms, logger)
    if dry_run:
        return report_dir

    suffix = yyyymmdd(selected_date)
    json_path = report_dir / f"literature_digest_{suffix}.json"
    md_path = report_dir / f"literature_digest_{suffix}.md"
    refined_path = report_dir / f"refined_literature_digest_{suffix}.json"
    audit_path = report_dir / f"literature_filtering_audit_{suffix}.md"
    refined_records = [refine_literature_record(record) for record in records]
    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    refined_path.write_text(json.dumps(refined_records, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(records, md_path, selected_date)
    write_filtering_audit(refined_records, audit_path, selected_date)
    logger.info("Wrote %s PubMed records to %s", len(records), json_path)
    logger.info("Wrote refined literature audit to %s", audit_path)
    return report_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MVP v0.1 PubMed literature digest.")
    parser.add_argument("--date", dest="run_date")
    parser.add_argument("--config", type=Path, default=Path("config/paths.yaml"))
    parser.add_argument("--outdir", type=Path)
    parser.add_argument("--retmax", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    outdir = run(args.run_date, args.config, args.outdir, args.dry_run, args.retmax)
    print(f"literature_watcher output: {outdir}")


if __name__ == "__main__":
    main()
