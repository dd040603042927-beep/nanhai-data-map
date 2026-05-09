import re
from pathlib import Path

from web_crawler_utils import (
    DATA_DIR,
    STANDARD_HEADERS,
    build_standard_row,
    extract_clean_text,
    fetch_html,
    load_enterprise_seed_rows,
    load_sample_reference_rows,
    search_bing_links,
    write_rows,
)

OUTPUT_PATH = DATA_DIR / "job_board_enrichment.csv"
STANDARD_OUTPUT_PATH = DATA_DIR / "job_board_standardized.csv"
ALLOWED_DOMAINS = ["zhipin.com", "liepin.com", "zhaopin.com", "51job.com"]
DATA_JOB_KEYWORDS = [
    "数据",
    "算法",
    "ai",
    "人工智能",
    "大数据",
    "建模",
    "分析",
    "平台",
    "安全",
    "云计算",
]


def choose_job_link(name: str) -> str:
    links = search_bing_links(f"{name} 招聘", allowed_domains=ALLOWED_DOMAINS, max_links=5)
    return links[0] if links else ""


def extract_job_keywords(text: str) -> str:
    text_lower = text.lower()
    hits = [keyword for keyword in DATA_JOB_KEYWORDS if keyword.lower() in text_lower]
    return "、".join(hits[:8])


def build_rows(limit: int | None = 50):
    rows = []
    standard_rows = []
    seed_rows = load_enterprise_seed_rows(limit=limit)
    sample_reference = load_sample_reference_rows()

    for seed in seed_rows:
        name = (seed.get("企业名称") or "").strip()
        job_url = choose_job_link(name)
        if not job_url:
            rows.append(
                {
                    "企业名称": name,
                    "招聘链接": "",
                    "岗位摘要": "",
                    "岗位关键词": "",
                    "岗位证据": "未检索到招聘页面",
                    "采集状态": "failed",
                }
            )
            continue

        try:
            html = fetch_html(job_url)
            clean_text = extract_clean_text(html, max_length=500)
            summary = clean_text[:220]
            keywords = extract_job_keywords(clean_text)
            evidence = re.sub(r"\s+", " ", clean_text)[:320]
            status = "success"
        except Exception as exc:
            summary = ""
            keywords = ""
            evidence = f"招聘信息抓取失败：{exc}"
            status = "failed"

        rows.append(
            {
                "企业名称": name,
                "招聘链接": job_url,
                "岗位摘要": summary,
                "岗位关键词": keywords,
                "岗位证据": evidence,
                "采集状态": status,
            }
        )
        standard_rows.append(
            build_standard_row(
                name=name,
                town=(seed.get("所在镇街") or "").strip(),
                seed_category=(seed.get("主要类型") or "").strip(),
                seed_product=(seed.get("主营产品") or "").strip() or keywords,
                source_url=job_url,
                source_label="招聘网站",
                summary=summary,
                evidence=evidence,
                sample_reference=sample_reference,
            )
        )

    return rows, standard_rows


def main():
    rows, standard_rows = build_rows()
    write_rows(
        OUTPUT_PATH,
        ["企业名称", "招聘链接", "岗位摘要", "岗位关键词", "岗位证据", "采集状态"],
        rows,
    )
    write_rows(STANDARD_OUTPUT_PATH, STANDARD_HEADERS, standard_rows)
    print(f"招聘岗位信息已输出到：{OUTPUT_PATH}")
    print(f"招聘标准化结果已输出到：{STANDARD_OUTPUT_PATH}")
    print(f"共处理 {len(rows)} 家企业")


if __name__ == "__main__":
    main()
