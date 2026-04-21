OFFICIAL_TOWNS = [
    "桂城街道",
    "狮山镇",
    "大沥镇",
    "里水镇",
    "丹灶镇",
    "西樵镇",
    "九江镇",
]

OFFICIAL_CATEGORIES = [
    "数据资源",
    "数据技术",
    "数据服务",
    "数据应用",
    "数据安全",
    "数据基础设施",
]

CATEGORY_ALIASES = {
    "数据资源": "数据资源",
    "数据资源类": "数据资源",
    "数据资源企业": "数据资源",
    "数据技术": "数据技术",
    "数据技术类": "数据技术",
    "数据技术企业": "数据技术",
    "数据服务": "数据服务",
    "数据服务类": "数据服务",
    "数据服务企业": "数据服务",
    "数据应用": "数据应用",
    "数据应用类": "数据应用",
    "数据应用企业": "数据应用",
    "数据安全": "数据安全",
    "数据安全类": "数据安全",
    "数据安全企业": "数据安全",
    "数据基础设施": "数据基础设施",
    "数据基础设施类": "数据基础设施",
    "数据基础设施企业": "数据基础设施",
    "其他数据相关类": "数据应用",
}


def normalize_town(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return "待补充"

    for town in OFFICIAL_TOWNS:
        if town in text:
            return town

    short_names = {
        "桂城": "桂城街道",
        "狮山": "狮山镇",
        "大沥": "大沥镇",
        "里水": "里水镇",
        "丹灶": "丹灶镇",
        "西樵": "西樵镇",
        "九江": "九江镇",
    }

    for short_name, full_name in short_names.items():
        if short_name in text:
            return full_name

    return "待补充"


def normalize_category(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return "待分类"

    return CATEGORY_ALIASES.get(text, text)
