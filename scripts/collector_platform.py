import csv
from pathlib import Path

SOURCE_REGISTRY = [
    {
        "id": "amap_poi",
        "name": "高德 POI",
        "status": "enabled",
        "description": "发现候选企业、地址、POI 类型。",
    },
    {
        "id": "company_website",
        "name": "企业官网",
        "status": "enabled",
        "description": "通过搜索引擎发现官网并抓取主营业务、产品与解决方案证据。",
    },
    {
        "id": "baike",
        "name": "百科信息",
        "status": "enabled",
        "description": "检索百科页面，补充企业简介与公开知识条目。",
    },
    {
        "id": "job_board",
        "name": "招聘网站",
        "status": "enabled",
        "description": "抓取招聘页面摘要，推断技术栈、岗位画像与数据业务方向。",
    },
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "multisource_registry.csv"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id", "name", "status", "description"],
        )
        writer.writeheader()
        writer.writerows(SOURCE_REGISTRY)

    print(f"已输出采集平台注册表：{OUTPUT_PATH}")
    print(f"当前注册数据源数量：{len(SOURCE_REGISTRY)}")


if __name__ == "__main__":
    main()
