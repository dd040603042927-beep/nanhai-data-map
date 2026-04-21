from pathlib import Path

from web_crawler_utils import (
    DATA_DIR,
    STANDARD_HEADERS,
    build_standard_row,
    extract_clean_text,
    extract_meta_description,
    fetch_html,
    load_enterprise_seed_rows,
    load_sample_reference_rows,
    search_bing_links,
    write_rows,
)

OUTPUT_PATH = DATA_DIR / "company_website_enrichment.csv"
STANDARD_OUTPUT_PATH = DATA_DIR / "company_website_standardized.csv"
EXCLUDED_DOMAINS = [
    "baike.baidu.com",
    "zhipin.com",
    "liepin.com",
    "zhaopin.com",
    "51job.com",
]


def choose_official_website(name: str) -> str:
    links = search_bing_links(f"{name} 官网", max_links=8)
    for link in links:
        if all(domain not in link for domain in EXCLUDED_DOMAINS):
            return link
    return ""


def build_rows(limit: int | None = 50):
    rows = []
    standard_rows = []
    seed_rows = load_enterprise_seed_rows(limit=limit)
    sample_reference = load_sample_reference_rows()

    for seed in seed_rows:
        name = (seed.get("企业名称") or "").strip()
        website_url = choose_official_website(name)
        if not website_url:
            rows.append(
                {
                    "企业名称": name,
                    "官网链接": "",
                    "官网摘要": "",
                    "官网证据": "未检索到可信官网链接",
                    "采集状态": "failed",
                }
            )
            continue

        try:
            html = fetch_html(website_url)
            summary = extract_meta_description(html) or extract_clean_text(html, max_length=220)
            evidence = extract_clean_text(html, max_length=320)
            status = "success"
        except Exception as exc:
            summary = ""
            evidence = f"官网抓取失败：{exc}"
            status = "failed"

        rows.append(
            {
                "企业名称": name,
                "官网链接": website_url,
                "官网摘要": summary,
                "官网证据": evidence,
                "采集状态": status,
            }
        )
        standard_rows.append(
            build_standard_row(
                name=name,
                town=(seed.get("所在镇街") or "").strip(),
                seed_category=(seed.get("主要类型") or "").strip(),
                seed_product=(seed.get("主营产品") or "").strip(),
                source_url=website_url,
                source_label="企业官网",
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
        ["企业名称", "官网链接", "官网摘要", "官网证据", "采集状态"],
        rows,
    )
    write_rows(STANDARD_OUTPUT_PATH, STANDARD_HEADERS, standard_rows)
    print(f"官网信息已输出到：{OUTPUT_PATH}")
    print(f"官网标准化结果已输出到：{STANDARD_OUTPUT_PATH}")
    print(f"共处理 {len(rows)} 家企业")


if __name__ == "__main__":
    main()
