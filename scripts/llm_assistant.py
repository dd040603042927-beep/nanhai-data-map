import json
import os
from pathlib import Path
from urllib import error, request

INPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_20.csv"


def fallback_summary(name: str, category: str, reason: str, products: str) -> dict:
    return {
        "summary": f"{name} 当前归类为{category}，分类依据为：{reason}，主营产品/服务为：{products}。",
        "label_suggestion": category,
        "provider": "local-rule",
    }


def call_llm(name: str, category: str, reason: str, products: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if not api_key:
        return fallback_summary(name, category, reason, products)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是产业图谱分析助手，请输出 JSON 格式摘要。",
            },
            {
                "role": "user",
                "content": (
                    f"企业名：{name}\n"
                    f"当前类型：{category}\n"
                    f"分类依据：{reason}\n"
                    f"主营产品：{products}\n"
                    "请输出 JSON：{\"summary\":\"...\",\"label_suggestion\":\"...\"}"
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
            "summary": parsed.get("summary", ""),
            "label_suggestion": parsed.get("label_suggestion", category),
            "provider": model,
        }
    except (error.URLError, error.HTTPError, json.JSONDecodeError, KeyError, TimeoutError):
        return fallback_summary(name, category, reason, products)


def main():
    if not INPUT_PATH.exists():
        print(f"未找到输入文件：{INPUT_PATH}")
        return

    import csv

    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader[:3])

    for row in rows:
        result = call_llm(
            row.get("企业名称", "").strip(),
            row.get("主要类型", "").strip(),
            row.get("分类依据", "").strip(),
            row.get("主营产品", "").strip(),
        )
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
