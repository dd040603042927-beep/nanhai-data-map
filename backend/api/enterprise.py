import re
import subprocess
import sys
from pathlib import Path
import os
import uuid
from datetime import datetime

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
    r"采集",
    r"收集",
    r"帮我采集",
    r"帮我收集",
]

MEANINGLESS_QUERY_KEYWORDS = {
    "",
    "查",
    "找",
    "搜",
    "查找",
    "查询",
    "搜索",
    "采集",
    "收集",
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
    clean_text = re.sub(r"[，。、“”'‘'；：,.!?！？/\\]+", " ", text.strip())
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


def classify_enterprise_text(name: str, description: str, products: str) -> tuple:
    """AI自动分类：根据企业名称和描述，返回(分类, 分类依据)"""
    combined_text = f"{name} {description} {products}"

    if any(x in combined_text for x in ["数据安全", "安全", "加密", "隐私", "风控", "等保", "网络安全", "身份认证"]):
        return "数据安全", f"{name}涉及数据安全相关业务，建议归类为数据安全企业"
    elif any(x in combined_text for x in ["数据中心", "云平台", "云计算", "算力", "机房", "通信", "网络基础设施", "传输", "存储"]):
        return "数据基础设施", f"{name}提供数据基础设施服务，建议归类为数据基础设施企业"
    elif any(x in combined_text for x in ["大数据", "分析", "算法", "建模", "软件开发", "工业互联网", "平台开发", "AI", "智能决策", "数据分析"]):
        return "数据技术", f"{name}从事数据技术研发，建议归类为数据技术企业"
    elif any(x in combined_text for x in ["数据服务", "政务", "金融服务", "环保", "智慧城市", "公共服务", "运营服务", "社保", "医疗", "教育"]):
        return "数据服务", f"{name}提供行业数据服务，建议归类为数据服务企业"
    elif any(x in combined_text for x in ["数据应用", "智能", "应用系统", "平台应用", "电商", "用户数据"]):
        return "数据应用", f"{name}推动数据应用落地，建议归类为数据应用企业"
    elif any(x in combined_text for x in ["数据采集", "数据库", "资源管理", "档案", "数据资产", "数据资源"]):
        return "数据资源", f"{name}开展数据资源管理业务，建议归类为数据资源企业"
    else:
        return "数据应用", f"{name}建议归类为数据应用企业，请人工复核"


def generate_batch_id() -> str:
    """生成唯一的采集批次ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"batch_{timestamp}_{short_uuid}"


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


@router.get("/candidates")
def get_candidates(
    batch: str | None = Query(default=None, description="按批次筛选，为空则返回最新批次的候选企业"),
    db: Session = Depends(get_db),
):
    """获取候选企业列表，默认只返回最新采集批次的数据"""

    if batch:
        # 按指定批次筛选
        items = db.query(models.Enterprise).filter(
            models.Enterprise.collect_batch == batch,
            models.Enterprise.reviewed == False,
        ).order_by(models.Enterprise.id.desc()).limit(50).all()
    else:
        # 获取最新批次
        latest_batch = db.query(models.Enterprise.collect_batch).filter(
            models.Enterprise.collect_batch != None,
            models.Enterprise.collect_batch != "",
        ).order_by(models.Enterprise.id.desc()).first()

        if latest_batch and latest_batch[0]:
            items = db.query(models.Enterprise).filter(
                models.Enterprise.collect_batch == latest_batch[0],
                models.Enterprise.reviewed == False,
            ).order_by(models.Enterprise.id.desc()).limit(50).all()
        else:
            # 没有批次信息，返回空（不再返回所有未复核的）
            items = []

    return {
        "success": True,
        "total": len(items),
        "batch": batch or (latest_batch[0] if latest_batch else ""),
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "town": normalize_town(item.town),
                "category": normalize_category(item.category),
                "category_reason": item.category_reason or "待补充",
                "products": item.products or "待补充",
                "source_url": item.source_url or "",
                "evidence": item.evidence or "",
                "selected": True,
            }
            for item in items
        ],
    }


@router.post("/candidates/approve")
def approve_candidates(
    ids: str = Query(..., description="要入库的企业ID，用逗号分隔"),
    db: Session = Depends(get_db),
):
    """批量确认候选企业入库（标记为已复核）"""
    id_list = [int(i.strip()) for i in ids.split(",") if i.strip()]

    approved = 0
    for item_id in id_list:
        item = db.query(models.Enterprise).filter(models.Enterprise.id == item_id).first()
        if item:
            if not item.category_reason or item.category_reason.strip() in ["待补充", ""]:
                if not item.category or item.category.strip() in ["待分类", ""]:
                    combined = f"{item.name} {item.products or ''} {item.evidence or ''}"
                    cat, reason = classify_enterprise_text(item.name, item.evidence or "", item.products or "")
                    item.category = cat
                    item.category_reason = reason
                else:
                    item.category_reason = f"{item.name}归类为{item.category}企业，已人工确认"
            item.reviewed = True
            approved += 1

    db.commit()
    return {"success": True, "approved_count": approved}


@router.delete("/candidates/reject")
def reject_candidates(
    ids: str = Query(..., description="要删除的企业ID，用逗号分隔"),
    db: Session = Depends(get_db),
):
    """批量删除不需要的候选企业"""
    id_list = [int(i.strip()) for i in ids.split(",") if i.strip()]

    rejected = 0
    for item_id in id_list:
        item = db.query(models.Enterprise).filter(models.Enterprise.id == item_id).first()
        if item:
            db.delete(item)
            rejected += 1

    db.commit()
    return {"success": True, "rejected_count": rejected}


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
        "search_engine": [
            PROJECT_ROOT / "scripts" / "import_csv.py",
            PROJECT_ROOT / "scripts" / "normalize_enterprises.py",
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
        os.pathsep + env.get("PYTHONPATH", "")
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
                "search_engine_source.py",
                "company_website_source.py",
                "baike_source.py",
                "job_board_source.py",
            }:
                collected += extract_count(r"共(?:生成|处理|发现)\s*(\d+)\s*[条家]", output)

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


@router.post("/smart-collect")
def smart_collect(
    instruction: str = Query(..., min_length=1, description="采集指令"),
    db: Session = Depends(get_db),
):
    """一键智能采集：根据指令自动调度多源数据采集+AI分类"""

    parsed = parse_query_text(instruction)

    # 生成本次采集的唯一批次ID
    batch_id = generate_batch_id()

    # 搜索引擎永远执行（免费），高德POI可选（需要Key）
    tasks_to_run = ["search_engine"]

    amap_key = os.getenv("AMAP_WEB_KEY", "").strip()
    if not amap_key:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if text.startswith("AMAP_WEB_KEY="):
                    amap_key = text.split("=", 1)[1].strip().strip("'\"")
                    break

    if amap_key:
        tasks_to_run.append("amap_poi")

    if parsed["keyword"] and parsed["keyword"] not in MEANINGLESS_QUERY_KEYWORDS:
        if "company_website" not in tasks_to_run:
            tasks_to_run.append("company_website")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (
        os.pathsep + env.get("PYTHONPATH", "")
    )

    # 构建更精准的搜索指令：传递分类的关键词而不是分类名
    instruction_parts = [instruction]
    if parsed["category"]:
        # 把分类名转换为具体的搜索关键词
        category_kw_map = {
            "数据资源": "数据采集 数据资产 数据库",
            "数据技术": "大数据 人工智能 软件开发 数据分析",
            "数据服务": "数据服务 数字化 智慧城市 金融科技",
            "数据应用": "智能系统 数字化解决方案 平台应用",
            "数据安全": "数据安全 网络安全 信息安全",
            "数据基础设施": "数据中心 云计算 云服务 通信",
        }
        category_kw = category_kw_map.get(parsed["category"], parsed["category"])
        instruction_parts.append(category_kw)
    if parsed["town"]:
        instruction_parts.append(parsed["town"])
    env["PLATFORM_INSTRUCTION"] = " ".join(instruction_parts).strip()

    collected_count = 0
    task_results = []

    for task_id in tasks_to_run:
        script_path = PLATFORM_TASKS.get(task_id)
        if not script_path or not script_path.exists():
            task_results.append({"task": task_id, "status": "skipped", "reason": "脚本未找到"})
            continue

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        output = (result.stdout or "") + (result.stderr or "")
        success = result.returncode == 0

        if not success and "AMAP_WEB_KEY" in output:
            task_results.append({
                "task": task_id,
                "status": "skipped",
                "reason": "缺少高德API Key，已跳过POI采集",
                "count": 0
            })
            continue

        match = re.search(r"共(?:生成|处理|发现)\s*(\d+)\s*[条家]", output)
        count = int(match.group(1)) if match else 0
        collected_count += count

        task_results.append({
            "task": task_id,
            "status": "success" if success else "failed",
            "count": count,
            "output": output[:500]
        })

    # 记录导入前的最大ID，用于后续标记新数据
    max_id_before = db.query(models.Enterprise.id).order_by(models.Enterprise.id.desc()).first()
    max_id_before = max_id_before[0] if max_id_before else 0

    import_script = PROJECT_ROOT / "scripts" / "import_csv.py"
    normalize_script = PROJECT_ROOT / "scripts" / "normalize_enterprises.py"

    imported_count = 0
    if import_script.exists():
        result = subprocess.run(
            [sys.executable, str(import_script)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        output = (result.stdout or "") + (result.stderr or "")
        match = re.search(r"成功导入：\s*(\d+)\s*条", output)
        imported_count = int(match.group(1)) if match else 0

    if normalize_script.exists():
        subprocess.run(
            [sys.executable, str(normalize_script)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    # 标记本次新导入的数据：ID大于之前最大ID的，打上本次批次标记
    new_items = db.query(models.Enterprise).filter(
        models.Enterprise.id > max_id_before
    ).all()

    for item in new_items:
        item.collect_batch = batch_id

    db.commit()

    # AI自动分类：只对本批次的新数据进行分类
    batch_items = db.query(models.Enterprise).filter(
        models.Enterprise.collect_batch == batch_id
    ).all()

    classified_count = 0
    for item in batch_items:
        suggested_category, draft_reason = classify_enterprise_text(
            item.name, item.evidence or "", item.products or ""
        )
        item.category = suggested_category
        item.category_reason = draft_reason
        classified_count += 1

    db.commit()

    new_candidates = len(batch_items)

    skipped_tasks = [t for t in task_results if t.get("status") == "skipped"]
    hint = ""
    if skipped_tasks:
        reasons = [t.get("reason", "") for t in skipped_tasks]
        hint = f"（{'；'.join(reasons)}）"

    return {
        "success": True,
        "instruction": instruction,
        "parsed": {
            "category": parsed["category"],
            "town": parsed["town"],
            "keyword": parsed["keyword"],
        },
        "batch_id": batch_id,
        "tasks_executed": tasks_to_run,
        "task_results": task_results,
        "collected_count": collected_count,
        "imported_count": imported_count,
        "classified_count": classified_count,
        "total_enterprises": db.query(models.Enterprise).count(),
        "new_candidates": new_candidates,
        "hint": hint,
        "message": f"采集完成：发现{collected_count}家，导入{imported_count}家，AI分类{classified_count}家。本次新增{new_candidates}家候选企业待审核{hint}",
        "review_hint": f"请在下方审核本次采集的 {new_candidates} 家候选企业",
    }