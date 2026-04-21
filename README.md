# 南海区数据产业图谱

本项目已经收敛为比赛要求的交付形态，目标是完成南海区数据产业图谱的整理、查询和演示。

当前版本聚焦三件事：

1. 统一企业数据字段，只保留比赛核心字段：企业名、所在镇街、主要类型、分类依据、主营产品。
2. 提供前端查询页面，支持文字查询、语音查询、按镇街筛选、按类型筛选。
3. 提供后端统计接口，展示六大类企业分布和当前数据覆盖进度。

## 目录结构

```text
nanhai-data-map/
├── backend/                # FastAPI 后端
├── frontend/               # React + Vite 前端
├── scripts/                # CSV 导入、字段规范化脚本
├── data/                   # 原始采集数据
├── enterprise.db           # SQLite 数据库
└── docs/                   # 辅助文档
```

## 运行方式

### 1. 启动后端

```bash
cd /mnt/d/mpb/nanhai-data-map
python3 -m uvicorn backend.main:app --reload
```

### 2. 启动前端

```bash
cd /mnt/d/mpb/nanhai-data-map/frontend
npm install
npm run dev
```

前端默认通过 Vite 代理访问后端 `/api`。

## 当前接口

- `GET /enterprises/`：分页查询企业
- `GET /enterprises/stats`：获取总量、六大类统计、镇街统计
- `GET /enterprises/query`：文本或语音识别结果的自然语言查询

## 数据脚本

```bash
cd /mnt/d/mpb/nanhai-data-map
python3 scripts/normalize_enterprises.py
python3 scripts/import_csv.py
```

## 当前数据状态

仓库内现有数据库记录数不足 1000 家，代码已经按照比赛要求整理完毕，但想满足“1000 家企业图谱”这一成绩目标，还需要继续补充企业采集与人工复核。
