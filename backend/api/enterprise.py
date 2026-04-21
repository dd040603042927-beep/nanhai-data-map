import re
import subprocess
import sys
from pathlib import Path
import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import models
from backend.constants import (
    CATEGORY_ALIASES,
    OFFICIAL_CATEGORIES,
    OFFICIAL_TOWNS,
    normalize_category,
    normalize_town,
)
from backend.database import get_db
from backend.enrichment import (
    SOURCE_REGISTRY,
    build_enterprise_insight,
    build_graph_payload,
    build_platform_overview,
)

router = APIRouter(prefix="/enterprises", tags=["enterprises"])
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIR = PROJECT_ROOT / "scripts"
PLATFORM_TASKS = {
    item["id"]: SCRIPT_DIR / item["script"]
    for item in SOURCE_REGISTRY
    if item.get("script")
}

QUERY_TOWN_ALIASES = {
    "桂城街道": "桂城街道",
    "桂城": "桂城街道",
    "狮山镇": "狮山镇",
    "狮山": "狮山镇",
    "大沥镇": "大沥镇",
    "大沥": "大沥镇",
    "里水镇": "里水镇",
    "里水": "里水镇",
    "丹灶镇": "丹灶镇",
    "丹灶": "丹灶镇",
    "西樵镇": "西樵镇",
    "西樵": "西樵镇",
    "九江镇": "九江镇",
    "九江": "九江镇",
}

QUERY_CATEGORY_ALIASES = {
    "数据资源企业": "数据资源",
    "数据资源类": "数据资源",
    "数据资源": "数据资源",
    "数据技术企业": "数据技术",
    "数据技术类": "数据技术",
    "数据技术": "数据技术",
    "数据服务企业": "数据服务",
    "数据服务类": "数据服务",
    "数据服务": "数据服务",
    "数据应用企业": "数据应用",
    "数据应用类": "数据应用",
    "数据应用": "数据应用",
    "数据安全企业": "数据安全",
    "数据安全类": "数据安全",
    "数据安全": "数据安全",
    "数据基础设施企业": "数据基础设施",
    "数据基础设施类": "数据基础设施",
    "数据基础设施": "数据基础设施",
}

QUERY_FILLER_PATTERNS = [
    r"帮我",
    r"帮忙",
    r"请帮我",
    r"我想",
    r"我要",
    r"我想要",
    r"查一下",
    r"查一查",
    r"找一下",
    r"搜一下",
    r"搜一搜",
    r"一下",
    r"查询",
    r"查找",
    r"搜索",
    r"检索",
    r"查",
    r"找",
    r"搜",
    r"看一下",
    r"看一看",
    r"看看",
    r"有没有",
    r"有哪些",
    r"相关的",
    r"相关",
    r"从事",
    r"做",
    r"的",
]

MEANINGLESS_QUERY_KEYWORDS = {
    "",
    "查",
    "找",
    "搜",
    "查找",
    "查询",
    "搜索",
    "企业",
    "公司",
    "单位",
    "商家",
    "名单",
}


def serialize_enterprise(item: models.Enterprise, all_items) -> dict:
    insight = build_enterprise_insight(item, all_items, enable_llm=False)
    return {
        "id": item.id,
        "name": (item.name or "").strip(),
        "town": normalize_town(item.town),
        "category": normalize_category(item.category),
        "category_reason": (item.category_reason or "").strip() or "待补充",
        "products": (item.products or "").strip() or "待补充",
        "data_sources": insight["data_sources"],
        "source_count": insight["source_count"],
        "source_links": insight["source_links"],
        "raw_evidence": insight["raw_evidence"],
        "evidence_summary": insight["evidence_summary"],
        "company_size": insight["company_size"],
        "profile_tags": insight["profile_tags"],
        "confidence_level": insight["confidence_level"],
        "chain_position": insight["chain_position"],
        "related_enterprises": insight["related_enterprises"],
    }


def apply_filters(
    query,
    category: str | None,
    town: str | None,
    keyword: str | None,
):
    if category and category != "全部":
        accepted_categories = [
            raw_name
            for raw_name, normalized in CATEGORY_ALIASES.items()
            if normalized == category
        ]
        query = query.filter(models.Enterprise.category.in_(accepted_categories))

    if town and town != "全部":
        query = query.filter(models.Enterprise.town.contains(town))

    if keyword:
        clean_keyword = keyword.strip()
        if clean_keyword:
            query = query.filter(models.Enterprise.name.contains(clean_keyword))

    return query


def parse_query_text(text: str) -> dict:
    clean_text = re.sub(r"[，。、“”‘’；：,.!?！？/\\]+", " ", text.strip())
    parsed_category = None
    parsed_town = None

    for raw_name in sorted(QUERY_CATEGORY_ALIASES, key=len, reverse=True):
        if raw_name in clean_text:
            parsed_category = QUERY_CATEGORY_ALIASES[raw_name]
            break

    for raw_name in sorted(QUERY_TOWN_ALIASES, key=len, reverse=True):
        if raw_name in clean_text:
            parsed_town = QUERY_TOWN_ALIASES[raw_name]
            break

    keyword = clean_text
    for value in sorted(
        list(QUERY_CATEGORY_ALIASES) + list(QUERY_TOWN_ALIASES),
        key=len,
        reverse=True,
    ):
        keyword = keyword.replace(value, " ")

    for pattern in QUERY_FILLER_PATTERNS:
        keyword = re.sub(pattern, " ", keyword)

    keyword = re.sub(r"\b(企业|公司|单位|商家|名单)\b", " ", keyword)
    keyword = re.sub(r"\s+", " ", keyword).strip()

    if keyword in MEANINGLESS_QUERY_KEYWORDS:
        keyword = ""

    if parsed_category and keyword in MEANINGLESS_QUERY_KEYWORDS:
        keyword = ""

    return {
        "category": parsed_category,
        "town": parsed_town,
        "keyword": keyword,
    }


@router.get("/")
def list_enterprises(
    category: str | None = Query(default=None),
    town: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    all_items = db.query(models.Enterprise).all()
    query = db.query(models.Enterprise)
    query = apply_filters(query, category, town, keyword)

    total = query.count()
    items = (
        query.order_by(models.Enterprise.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_enterprise(item, all_items) for item in items],
    }


@router.get("/stats")
def get_enterprise_stats(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()

    category_stats = {category: 0 for category in OFFICIAL_CATEGORIES}
    town_stats = {town: 0 for town in OFFICIAL_TOWNS}

    for item in items:
        category = normalize_category(item.category)
        town = normalize_town(item.town)

        if category in category_stats:
            category_stats[category] += 1
        if town in town_stats:
            town_stats[town] += 1

    return {
        "total": len(items),
        "target": 1000,
        "category_stats": category_stats,
        "town_stats": town_stats,
    }


@router.get("/query")
def query_enterprises(
    text: str = Query(..., min_length=1, description="文本或语音识别结果"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    parsed = parse_query_text(text)

    all_items = db.query(models.Enterprise).all()
    query = db.query(models.Enterprise)
    query = apply_filters(
        query,
        parsed["category"],
        parsed["town"],
        parsed["keyword"],
    )

    total = query.count()
    items = (
        query.order_by(models.Enterprise.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "input": text,
        "parsed": parsed,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_enterprise(item, all_items) for item in items],
    }


@router.get("/{enterprise_id}/insight")
def get_enterprise_insight(
    enterprise_id: int,
    enable_llm: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    all_items = db.query(models.Enterprise).all()
    item = next((enterprise for enterprise in all_items if enterprise.id == enterprise_id), None)

    if not item:
        return {"success": False, "message": "企业不存在"}

    return {
        "success": True,
        "enterprise": serialize_enterprise(item, all_items),
        "insight": build_enterprise_insight(item, all_items, enable_llm=enable_llm),
    }


@router.get("/graph/network")
def get_enterprise_graph(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()
    return build_graph_payload(items)


@router.get("/platform/overview")
def get_platform_overview(db: Session = Depends(get_db)):
    items = db.query(models.Enterprise).all()
    return build_platform_overview(items)


@router.post("/platform/run")
def run_platform_task(
    task: str = Query(..., description="平台任务 id"),
    instruction: str | None = Query(default=None, description="平台任务指令"),
):
    script_path = PLATFORM_TASKS.get(task)
    if not script_path or not script_path.exists():
        return {"success": False, "message": f"未找到任务：{task}"}

    follow_up_scripts = {
        "amap_poi": [
            PROJECT_ROOT / "scripts" / "import_csv.py",
            PROJECT_ROOT / "scripts" / "normalize_enterprises.py",
            PROJECT_ROOT / "scripts" / "build_standardized_crawler_pool.py",
            PROJECT_ROOT / "scripts" / "collector_platform.py",
        ],
        "company_website": [
            PROJECT_ROOT / "scripts" / "build_standardized_crawler_pool.py",
            PROJECT_ROOT / "scripts" / "merge_multisource_enrichment.py",
            PROJECT_ROOT / "scripts" / "collector_platform.py",
        ],
        "baike": [
            PROJECT_ROOT / "scripts" / "build_standardized_crawler_pool.py",
            PROJECT_ROOT / "scripts" / "merge_multisource_enrichment.py",
            PROJECT_ROOT / "scripts" / "collector_platform.py",
        ],
        "job_board": [
            PROJECT_ROOT / "scripts" / "build_standardized_crawler_pool.py",
            PROJECT_ROOT / "scripts" / "merge_multisource_enrichment.py",
            PROJECT_ROOT / "scripts" / "collector_platform.py",
        ],
    }

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    if instruction:
        env["PLATFORM_INSTRUCTION"] = instruction.strip()
    env.setdefault("PLATFORM_LIMIT", "30")

    script_results = []

    def extract_count(pattern: str, text: str) -> int:
        match = re.search(pattern, text)
        return int(match.group(1)) if match else 0

    def build_error_message(output: str, script_name: str) -> str:
        clean_output = (output or "").strip()
        if "AMAP_WEB_KEY" in clean_output:
            return "高德 POI 采集失败：请在后端环境变量里配置 AMAP_WEB_KEY，或在项目根目录 .env.local / .env 中填写。"
        if "ModuleNotFoundError" in clean_output:
            missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", clean_output)
            if missing:
                return f"{script_name} 执行失败：缺少依赖 {missing.group(1)}。"
            return f"{script_name} 执行失败：缺少 Python 依赖。"
        if "NameResolutionError" in clean_output or "Failed to resolve" in clean_output:
            return f"{script_name} 执行失败：当前网络无法解析目标站点。"
        if "ConnectTimeout" in clean_output or "ReadTimeout" in clean_output or "timeout" in clean_output.lower():
            return f"{script_name} 执行失败：请求超时，请稍后重试。"

        lines = [line.strip() for line in clean_output.splitlines() if line.strip()]
        for line in reversed(lines):
            if "Traceback" in line:
                continue
            if line.startswith("File "):
                continue
            return line[:160]
        return f"{script_name} 执行失败。"

    def build_summary(results: list[dict]) -> dict:
        collected = 0
        imported = 0
        merged = 0

        for item in results:
            output = item.get("output", "")
            script_name = item.get("script", "")

            if script_name in {
                "amap_poi_source.py",
                "company_website_source.py",
                "baike_source.py",
                "job_board_source.py",
            }:
                collected += extract_count(r"共(?:生成|处理)\s*(\d+)\s*[条家]", output)

            if script_name == "import_csv.py":
                imported += extract_count(r"成功导入：\s*(\d+)\s*条", output)

            if script_name == "merge_multisource_enrichment.py":
                merged += extract_count(r"共更新\s*(\d+)\s*家企业", output)

        return {
            "collected_count": collected,
            "imported_count": imported,
            "merged_count": merged,
        }

    def execute_script(current_script_path: Path):
        result = subprocess.run(
            [sys.executable, str(current_script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        output = "\n".join(
            part for part in [result.stdout.strip(), result.stderr.strip()] if part
        )
        script_results.append(
            {
                "script": current_script_path.name,
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "output": output or "脚本已执行，但没有输出内容。",
                "message": (
                    "执行成功"
                    if result.returncode == 0
                    else build_error_message(output, current_script_path.name)
                ),
            }
        )
        return result.returncode == 0

    success = execute_script(script_path)
    if success:
        for extra_script in follow_up_scripts.get(task, []):
            if not extra_script.exists():
                script_results.append(
                    {
                        "script": extra_script.name,
                        "success": False,
                        "returncode": -1,
                        "output": f"缺少后处理脚本：{extra_script.name}",
                    }
                )
                success = False
                break
            if not execute_script(extra_script):
                success = False
                break

    output = "\n\n".join(
        f"[{item['script']}]\n{item['output']}" for item in script_results
    )

    return {
        "success": success,
        "task": task,
        "instruction": instruction or "",
        "returncode": 0 if success else next(
            (
                item["returncode"]
                for item in reversed(script_results)
                if not item["success"]
            ),
            1,
        ),
        "output": output or "任务已执行，但没有输出内容。",
        "steps": script_results,
        "summary": build_summary(script_results),
        "message": (
            "平台任务执行完成"
            if success
            else next(
                (item["message"] for item in reversed(script_results) if not item["success"]),
                "平台任务执行失败",
            )
        ),
        "auto_refresh_hint": "任务完成后请刷新企业列表、统计卡片和知识图谱。",
    }
