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

OUTPUT_PATH = DATA_DIR / "baike_enrichment.csv"
STANDARD_OUTPUT_PATH = DATA_DIR / "baike_standardized.csv"
ALLOWED_DOMAINS = ["baike.baidu.com", "baike.com", "wiki.mbalib.com"]


def choose_baike_link(name: str) -> str:
    links = search_bing_links(f"{name} 百度百科", allowed_domains=ALLOWED_DOMAINS, max_links=5)
    return links[0] if links else ""


def build_rows(limit: int | None = 50):
    rows = []
    standard_rows = []
    seed_rows = load_enterprise_seed_rows(limit=limit)
    sample_reference = load_sample_reference_rows()

    for seed in seed_rows:
        name = (seed.get("企业名称") or "").strip()
        baike_url = choose_baike_link(name)
        if not baike_url:
            rows.append(
                {
                    "企业名称": name,
                    "百科链接": "",
                    "百科摘要": "",
                    "百科证据": "未检索到百科页面",
                    "采集状态": "failed",
                }
            )
            continue

        try:
            html = fetch_html(baike_url)
            summary = extract_clean_text(html, max_length=220)
            evidence = extract_clean_text(html, max_length=320)
            status = "success"
        except Exception as exc:
            summary = ""
            evidence = f"百科抓取失败：{exc}"
            status = "failed"

        rows.append(
            {
                "企业名称": name,
                "百科链接": baike_url,
                "百科摘要": summary,
                "百科证据": evidence,
                "采集状态": status,
            }
        )
        standard_rows.append(
            build_standard_row(
                name=name,
                town=(seed.get("所在镇街") or "").strip(),
                seed_category=(seed.get("主要类型") or "").strip(),
                seed_product=(seed.get("主营产品") or "").strip(),
                source_url=baike_url,
                source_label="百科信息",
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
        ["企业名称", "百科链接", "百科摘要", "百科证据", "采集状态"],
        rows,
    )
    write_rows(STANDARD_OUTPUT_PATH, STANDARD_HEADERS, standard_rows)
    print(f"百科信息已输出到：{OUTPUT_PATH}")
    print(f"百科标准化结果已输出到：{STANDARD_OUTPUT_PATH}")
    print(f"共处理 {len(rows)} 家企业")


if __name__ == "__main__":
    main()
