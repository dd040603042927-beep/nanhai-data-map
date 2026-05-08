import json
import os
from collections import Counter
from urllib import error, request

from backend.constants import normalize_category, normalize_town

SOURCE_REGISTRY = [
    {
        "id": "search_engine",
        "name": "🔎 多源搜索引擎",
        "type": "公开搜索",
        "status": "已接入",
        "description": "通过天眼查/企查查/招聘/采购/协会等公开渠道批量发现企业",
        "script": "search_engine_source.py",
        "action_label": "搜索发现",
    },
    {
        "id": "amap_poi",
        "name": "🔍 高德POI发现",
        "type": "地图公开数据",
        "status": "已接入",
        "description": "批量发现南海区内候选数据企业与地址线索，帮你凑齐1000家名单",
        "script": "amap_poi_source.py",
        "action_label": "发现候选企业",
    },
    {
        "id": "company_website",
        "name": "📝 官网快照提取",
        "type": "企业公开信息",
        "status": "已接入",
        "description": "自动提取企业官网的核心业务描述，为分类依据提供证据引用",
        "script": "company_website_source.py",
        "action_label": "提取官网快照",
    },
    {
        "id": "ai_classify",
        "name": "🤖 AI分类建议",
        "type": "AI智能体",
        "status": "已接入",
        "description": "基于企业描述文字，自动推荐六大分类并生成分类依据草稿",
        "script": "",
        "action_label": "获取AI建议",
    },
    {
        "id": "job_board",
        "name": "📊 企业画像补全",
        "type": "岗位数据",
        "status": "已接入",
        "description": "补全企业规模、产业链位置等加分项字段",
        "script": "job_board_source.py",
        "action_label": "补全企业画像",
    },
]

CATEGORY_CHAIN_POSITION = {
    "数据资源": "上游",
    "数据基础设施": "上游",
    "数据技术": "中游",
    "数据安全": "中游",
    "数据服务": "下游",
    "数据应用": "下游",
}

CATEGORY_FLOW = {
    "数据资源": {"downstream": ["数据技术", "数据服务"]},
    "数据基础设施": {"downstream": ["数据技术", "数据安全"]},
    "数据技术": {"upstream": ["数据资源", "数据基础设施"], "downstream": ["数据服务", "数据应用"]},
    "数据安全": {"upstream": ["数据基础设施"], "downstream": ["数据服务", "数据应用"]},
    "数据服务": {"upstream": ["数据技术", "数据安全", "数据资源"], "downstream": ["数据应用"]},
    "数据应用": {"upstream": ["数据技术", "数据服务", "数据安全"]},
}


def split_text_list(text: str | None) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []

    separators = ["；", ";", "，", ",", "\n", "|"]
    values = [raw]
    for separator in separators:
        temp = []
        for value in values:
            temp.extend(value.split(separator))
        values = temp

    return [value.strip() for value in values if value.strip()]


def split_url_list(text: str | None) -> list[str]:
    return [value for value in split_text_list(text) if value.startswith("http")]


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def infer_data_sources(item) -> list[str]:
    sources = split_text_list(getattr(item, "data_sources", None))
    if sources:
        return dedupe_keep_order(sources)

    source_url = (getattr(item, "source_url", "") or "").lower()
    evidence = (getattr(item, "evidence", "") or "").lower()
    merged_text = f"{source_url} {evidence}"
    inferred = []

    if "高德" in merged_text or "amap" in merged_text or "poi" in merged_text:
        inferred.append("高德 POI")
    if "官网" in merged_text or "http://" in merged_text or "https://" in merged_text:
        inferred.append("企业官网")
    if "百科" in merged_text:
        inferred.append("百科信息")
    if "招聘" in merged_text or "岗位" in merged_text or "job" in merged_text:
        inferred.append("招聘网站")
    if "天眼查" in merged_text or "企查查" in merged_text or "搜索" in merged_text:
        inferred.append("搜索引擎")

    if not inferred:
        inferred.append("公开资料")

    return dedupe_keep_order(inferred)


def infer_source_count(item, sources: list[str]) -> int:
    stored = getattr(item, "source_count", None)
    if isinstance(stored, int) and stored > 0:
        return stored
    return len(sources)


def infer_source_links(item) -> list[str]:
    return dedupe_keep_order(split_url_list(getattr(item, "source_url", None)))


def infer_raw_evidence(item) -> list[str]:
    evidence = split_text_list(getattr(item, "evidence", None))
    if evidence:
        return dedupe_keep_order(evidence)[:6]
    return []


def infer_company_size(item) -> str:
    stored = (getattr(item, "company_size", "") or "").strip()
    if stored:
        return stored

    name = getattr(item, "name", "") or ""
    merged = f"{name} {getattr(item, 'products', '')} {getattr(item, 'evidence', '')}"

    if any(keyword in merged for keyword in ["集团", "股份", "控股", "上市"]):
        return "大型"
    if any(keyword in merged for keyword in ["科技", "信息", "数字", "网络"]):
        return "成长型"
    return "中小型"


def infer_profile_tags(item, sources: list[str], chain_position: str) -> list[str]:
    stored = split_text_list(getattr(item, "profile_tags", None))
    if stored:
        return dedupe_keep_order(stored)

    tags = [
        normalize_category(getattr(item, "category", "")),
        normalize_town(getattr(item, "town", "")),
        chain_position,
        f"{len(sources)}源佐证",
    ]

    if getattr(item, "reviewed", False):
        tags.append("人工复核")

    if getattr(item, "confidence", 0) >= 0.8:
        tags.append("高可信")
    elif getattr(item, "confidence", 0) >= 0.6:
        tags.append("中可信")
    else:
        tags.append("待加强")

    return dedupe_keep_order(tags)


def infer_confidence_level(item, source_count: int) -> str:
    stored = (getattr(item, "confidence_level", "") or "").strip()
    if stored:
        return stored

    # 人工复核过的，直接最高可信度
    if getattr(item, "reviewed", False):
        return "高"

    # 按置信度数值判断
    conf = getattr(item, "confidence", 0) or 0
    if conf >= 0.8:
        return "高"
    if conf >= 0.6:
        return "中"

    # 按来源数量判断
    if source_count >= 3:
        return "高"
    if source_count >= 2:
        return "中"
    if source_count >= 1:
        return "中"  # 至少有一个来源，默认中等可信

    return "低"


def infer_chain_position(item) -> str:
    stored = (getattr(item, "chain_position", "") or "").strip()
    if stored:
        return stored

    category = normalize_category(getattr(item, "category", ""))
    return CATEGORY_CHAIN_POSITION.get(category, "中游")


def infer_evidence_summary(item, sources: list[str]) -> str:
    stored = (getattr(item, "evidence_summary", "") or "").strip()
    if stored:
        return stored

    category = normalize_category(getattr(item, "category", ""))
    town = normalize_town(getattr(item, "town", ""))
    products = (getattr(item, "products", "") or "").strip() or "待补充"
    reason = (getattr(item, "category_reason", "") or "").strip() or "待补充"
    return (
        f"{getattr(item, 'name', '')} 位于{town}，归类为{category}。"
        f" 主要产品/服务：{products}。"
        f" 分类依据：{reason}。"
        f" 当前证据来源：{'、'.join(sources)}。"
    )


def score_relatedness(base_item, candidate) -> int:
    score = 0
    if base_item.id == candidate.id:
        return score

    if normalize_town(base_item.town) == normalize_town(candidate.town):
        score += 2
    if normalize_category(base_item.category) == normalize_category(candidate.category):
        score += 3

    base_products = split_text_list(base_item.products)
    candidate_products = split_text_list(candidate.products)
    if set(base_products) & set(candidate_products):
        score += 2

    return score


def build_relation_lists(item, all_items) -> dict:
    category = normalize_category(getattr(item, "category", ""))
    relation_rule = CATEGORY_FLOW.get(category, {})

    upstream = []
    downstream = []
    related_candidates = []

    for candidate in all_items:
        if candidate.id == item.id:
            continue

        candidate_category = normalize_category(getattr(candidate, "category", ""))
        score = score_relatedness(item, candidate)
        if score > 0:
            related_candidates.append((score, candidate.name))

        if candidate_category in relation_rule.get("upstream", []):
            if normalize_town(candidate.town) == normalize_town(item.town):
                upstream.append(candidate.name)

        if candidate_category in relation_rule.get("downstream", []):
            if normalize_town(candidate.town) == normalize_town(item.town):
                downstream.append(candidate.name)

    related_candidates.sort(key=lambda row: (-row[0], row[1]))

    return {
        "upstream": dedupe_keep_order(upstream)[:5],
        "downstream": dedupe_keep_order(downstream)[:5],
        "related": dedupe_keep_order([name for _, name in related_candidates])[:6],
    }


def fallback_llm_summary(item, evidence_summary: str, related: list[str]) -> dict:
    category = normalize_category(getattr(item, "category", ""))
    provider = "local-rule"
    llm_summary = (
        f"{getattr(item, 'name', '')} 可视为{category}方向企业。"
        f" {evidence_summary}"
    )
    if related:
        llm_summary += f" 结合镇街与业务相似度，推荐重点关注关联企业：{'、'.join(related[:3])}。"

    return {
        "provider": provider,
        "summary": llm_summary,
        "label_suggestion": category,
    }


def call_optional_llm(item, evidence_summary: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if not api_key:
        return fallback_llm_summary(item, evidence_summary, [])

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是产业图谱分析助手。请根据企业资料给出一句简短摘要，并输出建议类型。",
            },
            {
                "role": "user",
                "content": (
                    f"企业名：{getattr(item, 'name', '')}\n"
                    f"镇街：{normalize_town(getattr(item, 'town', ''))}\n"
                    f"当前类型：{normalize_category(getattr(item, 'category', ''))}\n"
                    f"分类依据：{getattr(item, 'category_reason', '')}\n"
                    f"主营产品：{getattr(item, 'products', '')}\n"
                    f"证据摘要：{evidence_summary}\n"
                    "请返回 JSON：{\"summary\":\"...\",\"label_suggestion\":\"...\"}"
                ),
            },
        ],
        "temperature": 0.2,
    }

    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return {
            "provider": model,
            "summary": parsed.get("summary") or evidence_summary,
            "label_suggestion": parsed.get("label_suggestion")
            or normalize_category(getattr(item, "category", "")),
        }
    except (error.URLError, error.HTTPError, KeyError, json.JSONDecodeError, TimeoutError):
        return fallback_llm_summary(item, evidence_summary, [])


def build_enterprise_insight(item, all_items, enable_llm: bool = False) -> dict:
    sources = infer_data_sources(item)
    source_count = infer_source_count(item, sources)
    chain_position = infer_chain_position(item)
    profile_tags = infer_profile_tags(item, sources, chain_position)
    confidence_level = infer_confidence_level(item, source_count)
    relation_lists = build_relation_lists(item, all_items)
    evidence_summary = infer_evidence_summary(item, sources)
    llm_result = (
        call_optional_llm(item, evidence_summary)
        if enable_llm
        else fallback_llm_summary(item, evidence_summary, relation_lists["related"])
    )

    return {
        "data_sources": sources,
        "source_count": source_count,
        "source_links": infer_source_links(item),
        "raw_evidence": infer_raw_evidence(item),
        "evidence_summary": evidence_summary,
        "company_size": infer_company_size(item),
        "profile_tags": profile_tags,
        "confidence_level": confidence_level,
        "chain_position": chain_position,
        "upstream_enterprises": relation_lists["upstream"],
        "downstream_enterprises": relation_lists["downstream"],
        "related_enterprises": relation_lists["related"],
        "llm_summary": (getattr(item, "llm_summary", "") or "").strip()
        or llm_result["summary"],
        "llm_label_suggestion": (getattr(item, "llm_label_suggestion", "") or "").strip()
        or llm_result["label_suggestion"],
        "llm_provider": (getattr(item, "llm_provider", "") or "").strip()
        or llm_result["provider"],
        "crawler_status": (getattr(item, "crawler_status", "") or "").strip() or "可扩展",
    }


def build_graph_payload(items) -> dict:
    nodes = []
    links = []
    added_nodes = set()

    category_index = {
        "企业": 0,
        "镇街": 1,
        "类型": 2,
    }

    def add_node(node_id: str, name: str, category: str, value: int):
        if node_id in added_nodes:
            return
        added_nodes.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "name": name,
                "category": category_index[category],
                "symbolSize": value,
            }
        )

    graph_items = items[:80]
    item_map = {item.name: item for item in graph_items}

    for item in graph_items:
        town = normalize_town(item.town)
        category = normalize_category(item.category)
        enterprise_node = f"enterprise:{item.id}"
        town_node = f"town:{town}"
        category_node = f"category:{category}"

        add_node(enterprise_node, item.name, "企业", 32)
        add_node(town_node, town, "镇街", 42)
        add_node(category_node, category, "类型", 42)

        links.append({"source": enterprise_node, "target": town_node, "value": "位于"})
        links.append({"source": enterprise_node, "target": category_node, "value": "归属"})

        relations = build_relation_lists(item, graph_items)["related"][:3]
        for related_name in relations:
            related_item = item_map.get(related_name)
            if not related_item:
                continue
            related_node = f"enterprise:{related_item.id}"
            add_node(related_node, related_item.name, "企业", 32)
            links.append({"source": enterprise_node, "target": related_node, "value": "关联"})

    categories = [
        {"name": "企业"},
        {"name": "镇街"},
        {"name": "类型"},
    ]
    return {"nodes": nodes, "links": links, "categories": categories}


def build_platform_overview(items) -> dict:
    source_counter = Counter()
    confidence_counter = Counter()
    chain_counter = Counter()

    for item in items:
        insight = build_enterprise_insight(item, items, enable_llm=False)
        for source in insight["data_sources"]:
            source_counter[source] += 1
        confidence_counter[insight["confidence_level"]] += 1
        chain_counter[insight["chain_position"]] += 1

    return {
        "sources": SOURCE_REGISTRY,
        "source_distribution": dict(source_counter),
        "confidence_distribution": dict(confidence_counter),
        "chain_distribution": dict(chain_counter),
        "platform_capabilities": [
            "多源搜索引擎采集",
            "多源数据采集",
            "证据摘要生成",
            "企业画像构建",
            "上下游关系推断",
            "知识图谱可视化",
            "可选 LLM 辅助分类与摘要",
        ],
        "agent_framework": {
            "name": "Nanhai Data Agent",
            "mode": "规则引擎 + 可选 LLM + 多源搜索",
            "status": "已集成基础框架",
        },
    }