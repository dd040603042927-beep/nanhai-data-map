"""ENScan_GO采集器"""
import re
import subprocess
from .base_collector import BaseCollector


class EnscanCollector(BaseCollector):
    """ENScan_GO采集器 - 使用天眼查数据源"""

    def __init__(self):
        super().__init__("ENScan_GO采集器", "enscan_enterprises.csv")

    def collect(self, **kwargs) -> list:
        parsed = self.parse_instruction()

        keywords = self._build_keywords(parsed)

        print(f"🏢 ENScan_GO采集: 镇街={parsed['town']}, 分类={parsed['category']}")

        for keyword in keywords:
            if len(self.results) >= parsed["limit"]:
                break
            self._search_enscan(keyword, parsed["limit"])

        self.save()
        return self.results

    def _build_keywords(self, parsed: dict) -> list:
        keywords = []

        if parsed["town"]:
            keywords.append(parsed["town"])

        category_map = {
            "数据资源": "数据资源",
            "数据技术": "数据技术",
            "数据服务": "数据服务",
            "数据应用": "数据应用",
            "数据安全": "数据安全",
            "数据基础设施": "基础设施",
        }

        if parsed["category"]:
            keywords.append(category_map.get(parsed["category"], parsed["category"]))

        if not keywords:
            keywords = ["数据技术"]

        return keywords[:3]

    def _search_enscan(self, keyword: str, limit: int):
        try:
            cmd = ["./enscan.exe", "-n", keyword, "-type", "tyc", "-deep", "1"]
            print(f"  执行: enscan -n {keyword} -type tyc")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='ignore'
            )

            output = result.stdout.strip()
            if not output:
                return

            # 解析输出，提取企业信息
            lines = output.split('\n')

            for line in lines:
                if len(self.results) >= limit:
                    break

                line = line.strip()
                if not line:
                    continue

                # 提取企业名称（常见格式：XXX有限公司、XXX公司等）
                patterns = [
                    r'([\u4e00-\u9fa5]+(?:有限公司|有限责任公司|股份有限公司|集团))',
                    r'([\u4e00-\u9fa5]+公司)',
                    r'([\u4e00-\u9fa5]+[数据科技信息]{2,}有限公司)',
                ]

                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        name = match.group(1)
                        if len(name) >= 6:
                            category = self._guess_category(name, line)

                            self.results.append({
                                "企业名称": name,
                                "所在镇街": self._extract_town(line),
                                "主要类型": f"{category}类",
                                "分类依据": f"ENScan_GO采集，关键词：{keyword}",
                                "主营产品": "待补充",
                                "数据来源": "ENScan_GO/天眼查",
                                "证据片段": line[:200],
                                "置信度": "0.75",
                                "是否人工复核": "false",
                            })
                            print(f"  ✓ {name}")
                            break

        except Exception as e:
            print(f"  ✗ 搜索失败: {e}")

    def _guess_category(self, name: str, context: str) -> str:
        text = f"{name} {context}".lower()

        if any(x in text for x in ["数据安全", "安全", "加密"]):
            return "数据安全"
        if any(x in text for x in ["数据中心", "云计算", "基础设施", "通信"]):
            return "数据基础设施"
        if any(x in text for x in ["大数据", "人工智能", "算法", "软件开发", "数据技术"]):
            return "数据技术"
        if any(x in text for x in ["数据服务", "信息服务", "服务"]):
            return "数据服务"
        if any(x in text for x in ["数据资源", "数据采集", "数据资产"]):
            return "数据资源"
        if "数据" in text:
            return "数据技术"
        return "数据技术"

    def _extract_town(self, text: str) -> str:
        towns = ["桂城", "狮山", "大沥", "里水", "丹灶", "西樵", "九江"]
        for town in towns:
            if town in text:
                if town == "桂城":
                    return "桂城街道"
                return f"{town}镇"
        return "待补充"


def main():
    collector = EnscanCollector()
    collector.collect()


if __name__ == "__main__":
    main()