from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models

router = APIRouter(prefix="/agent", tags=["agent"])


# ---------------------------
# 工具函数
# ---------------------------

TOWN_LIST = [
    "桂城街道",
    "狮山镇",
    "大沥镇",
    "里水镇",
    "丹灶镇",
    "西樵镇",
    "九江镇",
]

CATEGORY_KEYWORDS = {
    "数据资源类": ["数据资源", "数据采集", "数据标注", "数据交易"],
    "数据技术类": ["数据技术", "算法", "建模", "AI", "人工智能", "分析", "平台", "工业互联网"],
    "数据服务类": ["数据服务", "智慧城市", "信息服务", "数字化服务", "咨询"],
    "数据安全类": ["数据安全", "安全", "隐私", "网络安全"],
    "数据基础设施类": ["数据中心", "云平台", "云计算", "机房", "存储", "算力"],
    "其他数据相关类": []
}


def detect_category(text: str) -> str:
    text = text.strip()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text.lower():
                return category
    return "其他数据相关类"


def detect_town(text: str) -> str:
    for town in TOWN_LIST:
        if town in text:
            return town
    return "待补充"


def detect_name(text: str) -> str:
    """
    非严格NLP，只做简单规则提取：
    - 优先提取“叫XXX”
    - 其次提取“公司，叫XXX”
    - 实在不行返回原句前半段
    """
    text = text.strip()

    if "叫" in text:
        after = text.split("叫", 1)[1]
        # 遇到这些词就截断
        for sep in ["，", ",", "在", "主营", "做", "是"]:
            if sep in after:
                after = after.split(sep, 1)[0]
        return after.strip()

    return "待命名企业"


def detect_products(text: str) -> str:
    if "主营" in text:
        after = text.split("主营", 1)[1]
        for sep in ["，", ",", "。"]:
            if sep in after:
                after = after.split(sep, 1)[0]
        return after.strip()

    if "做" in text:
        after = text.split("做", 1)[1]
        for sep in ["，", ",", "在", "叫", "。"]:
            if sep in after:
                after = after.split(sep, 1)[0]
        return after.strip()

    return "待补充"


def build_stats_summary(stats: dict) -> str:
    category_map = {
        "数据服务类": stats.get("service", 0),
        "数据技术类": stats.get("tech", 0),
        "数据安全类": stats.get("security", 0),
        "数据基础设施类": stats.get("infrastructure", 0),
        "其他数据相关类": stats.get("other", 0),
    }

    max_category = max(category_map, key=category_map.get)
    max_count = category_map[max_category]
    total = stats.get("total", 0)

    ratio = 0
    if total > 0:
        ratio = round(max_count / total * 100, 1)

    return f"{max_category}企业最多，共{max_count}家，占比约{ratio}%"


# ---------------------------
# 1. 智能导入
# ---------------------------

@router.get("/import")
def agent_import(
    text: str = Query(..., description="自然语言输入，例如：帮我加一家做智慧城市的公司，叫南海智联科技，在桂城街道，主营智慧城市平台"),
    db: Session = Depends(get_db),
):
    name = detect_name(text)
    town = detect_town(text)
    category = detect_category(text)
    products = detect_products(text)

    # 重名检查
    existing = db.query(models.Enterprise).filter(models.Enterprise.name == name).first()
    if existing:
        return {
            "success": False,
            "message": f"企业“{name}”已存在，未重复导入",
            "parsed": {
                "name": name,
                "town": town,
                "category": category,
                "products": products,
            }
        }

    enterprise = models.Enterprise(
        name=name,
        town=town,
        category=category,
        category_reason=f"Agent根据自然语言关键词自动判断为{category}",
        products=products,
        source_url="Agent输入",
        evidence=text,
        confidence=0.75,
        reviewed=False,
    )

    db.add(enterprise)
    db.commit()
    db.refresh(enterprise)

    return {
        "success": True,
        "message": "智能导入成功",
        "parsed": {
            "id": enterprise.id,
            "name": enterprise.name,
            "town": enterprise.town,
            "category": enterprise.category,
            "products": enterprise.products,
        }
    }


# ---------------------------
# 2. 智能搜索
# ---------------------------

@router.get("/search")
def agent_search(
    text: str = Query(..., description="自然语言输入，例如：帮我找南海区做数据安全的企业"),
    db: Session = Depends(get_db),
):
    category = detect_category(text)
    town = detect_town(text)

    query = db.query(models.Enterprise)

    # 如果识别到类别就按类别查
    if category and category != "其他数据相关类":
        query = query.filter(models.Enterprise.category == category)

    # 如果识别到镇街就按镇街查
    if town and town != "待补充":
        query = query.filter(models.Enterprise.town == town)

    items = query.limit(20).all()

    return {
        "input": text,
        "parsed": {
            "category": category,
            "town": town,
        },
        "count": len(items),
        "results": [
            {
                "id": item.id,
                "name": item.name,
                "town": item.town,
                "category": item.category,
                "products": item.products,
            }
            for item in items
        ]
    }


# ---------------------------
# 3. 智能统计问答
# ---------------------------

@router.get("/stats")
def agent_stats(db: Session = Depends(get_db)):
    total = db.query(models.Enterprise).count()

    service = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据服务类"
    ).count()

    tech = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据技术类"
    ).count()

    security = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据安全类"
    ).count()

    infrastructure = db.query(models.Enterprise).filter(
        models.Enterprise.category == "数据基础设施类"
    ).count()

    other = db.query(models.Enterprise).filter(
        models.Enterprise.category == "其他数据相关类"
    ).count()

    stats = {
        "total": total,
        "service": service,
        "tech": tech,
        "security": security,
        "infrastructure": infrastructure,
        "other": other,
    }

    summary = build_stats_summary(stats)

    return {
        "stats": stats,
        "summary": summary
    }