"""基础采集器"""
import csv
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


class BaseCollector(ABC):
    """采集器基类"""
    
    def __init__(self, name: str, output_file: str):
        self.name = name
        self.output_path = DATA_DIR / output_file
        self.results = []
        
    @abstractmethod
    def collect(self, **kwargs) -> list:
        """执行采集"""
        pass
    
    def save(self):
        """保存结果"""
        if not self.results:
            print(f"⚠️ {self.name}: 无数据可保存")
            return
        
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        fieldnames = [
            "企业名称", "所在镇街", "主要类型", "分类依据",
            "主营产品", "数据来源", "证据片段", "置信度", "是否人工复核"
        ]
        
        with open(self.output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)
        
        print(f"✅ {self.name}: 保存 {len(self.results)} 条数据 -> {self.output_path}")
    
    def parse_instruction(self) -> dict:
        """解析采集指令"""
        instruction = os.getenv("PLATFORM_INSTRUCTION", "")
        limit = int(os.getenv("PLATFORM_LIMIT", "50"))
        
        towns = ["桂城街道", "狮山镇", "大沥镇", "里水镇", "丹灶镇", "西樵镇", "九江镇"]
        found_town = ""
        for town in towns:
            if town in instruction:
                found_town = town
                break
        
        categories = ["数据资源", "数据技术", "数据服务", "数据应用", "数据安全", "数据基础设施"]
        found_category = ""
        for cat in categories:
            if cat in instruction:
                found_category = cat
                break
        
        return {
            "instruction": instruction,
            "town": found_town,
            "category": found_category,
            "limit": limit
        }
    
    def normalize_name(self, name: str) -> str:
        if not name:
            return ""
        text = re.sub(r"[（(].*?[）)]", "", name)
        text = re.sub(r"\s+", "", text)
        return text.lower()
