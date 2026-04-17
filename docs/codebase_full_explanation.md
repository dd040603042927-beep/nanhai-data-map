# nanhai-data-map 全项目代码详解

## 1. 文档目的

这份文档用于系统解释 `nanhai-data-map` 项目中“项目自己编写的代码和关键配置文件”。

你的原始要求是“读取里面所有的文件，并把所有代码详细解释清楚写入文件中”。  
项目目录里同时包含了这些内容：

- 项目源码
- 项目文档
- CSV 数据文件
- SQLite 数据库
- 图片截图
- `node_modules` 第三方依赖
- `.git` 版本控制元数据
- `__pycache__` 字节码缓存

其中真正值得逐段解释的是“项目自己的源码和配置”。如果把 `node_modules` 和 `.git` 也逐个展开，不仅数量极大，而且绝大部分都不是这个项目本身写的逻辑，会严重干扰阅读。

所以这份文档的解释范围是：

- 后端源码
- 前端源码
- 数据处理脚本
- 关键配置文件
- 关键数据文件和文档文件的用途说明

不做逐段解释但会说明用途的范围是：

- `node_modules/`
- `.git/`
- `__pycache__/`
- `enterprise.db`
- `docs/screenshots/`
- 图片资源和 favicon

---

## 2. 项目整体是做什么的

这个项目本质上是一个“南海区数据产业企业图谱”的小型全栈系统。

它的完整流程可以理解成 4 步：

1. 通过高德 POI 接口按关键词抓取企业候选数据
2. 把抓到的候选数据整理成 CSV，再导入 SQLite 数据库
3. 用 FastAPI 把企业数据、筛选、分页、统计接口暴露出来
4. 用 React + Ant Design + ECharts 做一个展示页面，供用户筛选、搜索、分页和看统计图

除此之外，项目还额外做了一个“规则式 agent 接口”，允许用户用自然语言完成：

- 智能导入
- 智能搜索
- 智能统计总结

所以从结构上看，这个项目分成 3 层：

- 数据采集层：`scripts/`
- 数据服务层：`backend/`
- 可视化展示层：`frontend/`

---

## 3. 目录结构说明

项目中和你自己代码最相关的目录如下：

```text
nanhai-data-map/
├── backend/                 # FastAPI 后端
│   ├── api/
│   │   ├── enterprise.py    # 企业数据接口
│   │   └── agent.py         # 自然语言规则接口
│   ├── database.py          # 数据库连接配置
│   ├── main.py              # 后端入口
│   ├── models.py            # SQLAlchemy 数据模型
│   └── schemas.py           # Pydantic 数据校验模型
├── frontend/                # React 前端
│   ├── src/
│   │   ├── App.jsx          # 主页面
│   │   ├── App.css          # 旧模板样式
│   │   ├── index.css        # 全局样式
│   │   └── main.jsx         # 前端入口
│   ├── package.json
│   ├── vite.config.js
│   ├── eslint.config.js
│   └── index.html
├── scripts/
│   ├── amap_poi_source.py   # 从高德抓企业候选数据
│   └── import_csv.py        # 把 CSV 导入数据库
├── data/
│   ├── amap_enterprises.csv
│   └── sample_20.csv
├── docs/                    # 项目说明文档
├── enterprise.db            # SQLite 数据库
├── README.md
└── requirements.txt
```

---

## 4. 后端代码详解

### 4.1 `backend/__init__.py`

这个文件是空文件。

它的作用不是写业务逻辑，而是告诉 Python：

- `backend` 是一个可导入的包
- 所以其他文件才能写 `from backend import models`

也就是说，它是包结构标记文件。

---

### 4.2 `backend/main.py`

这个文件是 FastAPI 应用入口。

源码作用可以拆成几部分：

#### 1. 导入依赖

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
```

这里导入了：

- `FastAPI`：用来创建 Web 应用
- `CORSMiddleware`：用来处理跨域请求

因为前端运行在 `localhost:5173`，后端运行在 `127.0.0.1:8000`，它们端口不同，所以浏览器会把它当成跨域访问。如果不加 CORS，中间很多请求会被浏览器拦住。

#### 2. 导入项目内部模块

```python
from backend import models
from backend.api.enterprise import router as enterprise_router
from backend.database import engine
from backend.api.agent import router as agent_router
```

这里分别拿到了：

- `models`：数据库表结构
- `enterprise_router`：企业接口路由
- `engine`：数据库连接引擎
- `agent_router`：智能体接口路由

#### 3. 自动建表

```python
models.Base.metadata.create_all(bind=engine)
```

这一句的含义非常重要：

- `Base.metadata` 收集了所有 SQLAlchemy 模型定义出来的表
- `create_all(bind=engine)` 会在数据库里自动创建尚不存在的表

所以当你第一次运行后端时，只要 `models.py` 里定义了 `Enterprise` 表，它就会自动在 `enterprise.db` 中建立这张表。

这个设计适合课程项目、小型原型和本地开发，因为不需要额外写复杂的迁移脚本。

#### 4. 创建应用对象

```python
app = FastAPI(
    title="Nanhai Data Map API",
    description="南海区数据产业企业图谱后端服务",
    version="1.0.0"
)
```

这里创建了 FastAPI 应用实例，并设置了接口文档里的基本信息。

这些内容会出现在：

- `/docs` Swagger 文档页面
- `/openapi.json`

#### 5. 配置跨域

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

这一段的意思是允许前端开发服务器访问后端接口。

具体来说：

- `allow_origins=["http://localhost:5173"]`
  只允许这个来源访问
- `allow_credentials=True`
  允许携带 cookie / 凭证
- `allow_methods=["*"]`
  所有 HTTP 方法都允许
- `allow_headers=["*"]`
  所有请求头都允许

这说明项目目前的默认联调场景是：

- 前端：Vite 默认地址 `http://localhost:5173`
- 后端：FastAPI 默认地址 `http://127.0.0.1:8000`

#### 6. 注册路由

```python
app.include_router(enterprise_router)
app.include_router(agent_router)
```

这一段把两个模块里的接口接入总应用中。

也就是说：

- `enterprise.py` 里的接口会挂到 `/enterprises/...`
- `agent.py` 里的接口会挂到 `/agent/...`

#### 7. 根路径健康检查

```python
@app.get("/")
def root():
    return {"message": "Nanhai Data Map API is running"}
```

这个接口的功能很简单，就是访问首页时返回一句“服务正在运行”。

它的典型用途是：

- 确认后端是否启动
- 给部署或演示时做快速健康检查

---

### 4.3 `backend/database.py`

这个文件专门管理数据库连接。

#### 1. `DATABASE_URL`

```python
DATABASE_URL = "sqlite:///./enterprise.db"
```

这说明项目使用的是 SQLite 数据库，并且数据库文件就在项目根目录下，名字叫：

```text
enterprise.db
```

SQLite 的优点是：

- 无需安装 MySQL / PostgreSQL
- 文件型数据库，适合教学和原型开发
- 启动门槛低

#### 2. `engine = create_engine(...)`

```python
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
```

这里创建数据库引擎。

关键点是：

- `check_same_thread=False`

SQLite 默认限制一个连接只能在创建它的线程中使用。  
而 FastAPI 在处理请求时可能涉及不同线程，因此这里把这个限制关掉，避免开发环境下报错。

#### 3. `SessionLocal`

```python
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
```

这是数据库会话工厂。

你可以把它理解成“每次请求需要数据库连接时，从这里造一个新的会话对象”。

两个参数含义：

- `autocommit=False`
  不自动提交，必须手动 `commit()`
- `autoflush=False`
  不自动把内存中的修改刷新到数据库，便于你显式控制写入时机

#### 4. `Base = declarative_base()`

这个 `Base` 是所有模型类的父类。

在 `models.py` 中：

```python
class Enterprise(Base):
```

这样 SQLAlchemy 才知道它是一个 ORM 模型，并把它纳入元数据管理。

#### 5. `get_db()`

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

这是给 FastAPI 的依赖注入系统用的。

它的工作方式是：

1. 先创建一个数据库会话 `db`
2. 把它 `yield` 给接口函数使用
3. 请求结束后不管成功失败，都执行 `db.close()`

所以在接口中常见：

```python
db: Session = Depends(get_db)
```

意思就是“请 FastAPI 自动帮我准备一个数据库会话”。

---

### 4.4 `backend/models.py`

这个文件定义数据库表结构。

目前只有一个模型类：`Enterprise`

#### 1. 表名

```python
__tablename__ = "enterprises"
```

表示这张表在数据库中实际叫 `enterprises`。

#### 2. 字段解释

```python
id = Column(Integer, primary_key=True, index=True)
```

- 主键
- 整数类型
- 自动作为每条记录唯一标识
- 建索引便于查询

```python
name = Column(String(255), nullable=False, index=True)
```

- 企业名称
- 最多 255 字符
- 必填
- 建索引，方便按名称查找

```python
town = Column(String(100), nullable=False, index=True)
```

- 所在镇街
- 必填
- 建索引，方便按区域筛选

```python
category = Column(String(100), nullable=False, index=True)
```

- 企业分类
- 对应 `taxonomy.md` 中的分类体系
- 建索引，方便分类统计和筛选

```python
category_reason = Column(Text, nullable=False)
```

- 分类依据
- 用来说明为什么这家企业被归入当前类别
- 是做数据可追溯的重要字段

```python
products = Column(Text, nullable=True)
```

- 主营产品或解决方案
- 允许为空

```python
source_url = Column(Text, nullable=True)
```

- 数据来源链接
- 可以是官网、新闻页、公开平台链接

```python
evidence = Column(Text, nullable=True)
```

- 证据片段
- 记录原始文本摘要，方便人工复核

```python
confidence = Column(Float, default=0.0)
```

- 置信度
- 一般用于表示分类结果的可信程度
- 默认值是 `0.0`

```python
reviewed = Column(Boolean, default=False)
```

- 是否已经人工复核
- 默认未复核

#### 3. 这张表的设计思路

这个表不是简单的“企业名录”，而是一个“可追溯的分类结果表”。

也就是说，它关心的不只是企业叫什么，还关心：

- 属于哪一类
- 为什么这么分
- 证据从哪里来
- 是否复核过

这正好匹配“高质量数据集”项目对可解释性和可追溯性的要求。

---

### 4.5 `backend/schemas.py`

这个文件定义接口层使用的 Pydantic 模型。

它和 `models.py` 的区别是：

- `models.py` 是数据库结构
- `schemas.py` 是接口入参和出参格式

#### 1. `EnterpriseBase`

```python
class EnterpriseBase(BaseModel):
```

这是公共字段基类。

它把创建和返回接口里都会用到的字段都集中定义了一次，避免重复写。

字段上的 `Field()` 主要做两件事：

- 指定默认值或校验规则
- 给 FastAPI 文档添加字段说明

例如：

```python
confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
```

这里不仅设置了默认值，还限制了：

- 不能小于 0
- 不能大于 1

所以如果前端传 `1.5`，FastAPI 会直接校验失败。

#### 2. `EnterpriseCreate`

```python
class EnterpriseCreate(EnterpriseBase):
    pass
```

这个类没有加新字段，只是语义上区分“创建请求模型”。

这样做的好处是：

- 以后如果创建接口需要特殊字段，很容易扩展
- 接口定义更直观

#### 3. `EnterpriseResponse`

```python
class EnterpriseResponse(EnterpriseBase):
    id: int
```

返回模型比创建模型多了 `id`，因为数据库写入成功后，会自动生成主键。

```python
class Config:
    from_attributes = True
```

这句非常关键，它允许 Pydantic 直接从 SQLAlchemy 对象读取字段。

如果没有它，像下面这种直接返回 ORM 对象的代码：

```python
return db_enterprise
```

有时不能正确序列化。

---

### 4.6 `backend/api/enterprise.py`

这个文件是企业数据的主接口。

#### 1. 路由对象

```python
router = APIRouter(prefix="/enterprises", tags=["enterprises"])
```

说明这里所有接口都会自动带上：

- 前缀 `/enterprises`
- 文档标签 `enterprises`

#### 2. `create_enterprise()`

```python
@router.post("/", response_model=schemas.EnterpriseResponse)
def create_enterprise(enterprise: schemas.EnterpriseCreate, db: Session = Depends(get_db)):
```

这是新增企业接口。

它的完整逻辑是：

1. 接收前端传入的 `EnterpriseCreate`
2. 用 `enterprise.model_dump()` 把 Pydantic 模型转成字典
3. 用这个字典构造 `models.Enterprise`
4. `db.add()` 加到会话中
5. `db.commit()` 提交到数据库
6. `db.refresh()` 把数据库最新值刷新回对象
7. 返回新增后的对象

为什么要 `refresh()`：

- 因为数据库插入后会生成 `id`
- 刷新后，返回对象里才带有最新主键值

#### 3. `list_enterprises()`

```python
@router.get("/")
def list_enterprises(...)
```

这是列表查询接口。

它支持多个查询参数：

- `category`
- `town`
- `keyword`
- `page`
- `page_size`

##### 查询流程

```python
query = db.query(models.Enterprise)
```

先从整张表开始查。

然后按条件逐层缩小范围：

```python
if category:
    query = query.filter(models.Enterprise.category == category)
```

按分类过滤。

```python
if town:
    query = query.filter(models.Enterprise.town == town)
```

按镇街过滤。

```python
if keyword:
    query = query.filter(models.Enterprise.name.contains(keyword))
```

按企业名做模糊包含查询。

##### 分页逻辑

```python
total = query.count()
```

先统计符合条件的总数量。

```python
items = (
    query.order_by(desc(models.Enterprise.id))
    .offset((page - 1) * page_size)
    .limit(page_size)
    .all()
)
```

这里完成分页：

- `order_by(desc(id))`：按 id 倒序，新的记录排前面
- `offset((page - 1) * page_size)`：跳过前面页的数据
- `limit(page_size)`：只取本页指定条数

##### 返回结构

这个接口没有直接返回 ORM 对象列表，而是手工拼了一个字典：

```python
{
    "total": total,
    "page": page,
    "page_size": page_size,
    "items": [...]
}
```

这样做的好处是：

- 前端拿到的数据结构更适合分页表格
- 比单纯返回数组更完整

#### 4. `get_enterprise_stats()`

```python
@router.get("/stats")
def get_enterprise_stats(db: Session = Depends(get_db)):
```

这个接口负责统计不同类别企业数量。

它分别计算：

- 企业总数
- 数据服务类
- 数据技术类
- 数据安全类
- 数据基础设施类
- 其他数据相关类

然后返回：

```python
{
    "total": total,
    "service": service,
    "tech": tech,
    "security": security,
    "infrastructure": infrastructure,
    "other": other,
}
```

这正是前端统计卡片和柱状图的数据来源。

#### 5. 这个文件的优点与限制

优点：

- 查询逻辑直观
- 支持分页、筛选、搜索
- 返回结构适合前端

限制：

- 统计接口每个类别都单独查一遍，效率一般
- 没有更新和删除接口
- 没有更复杂的排序能力
- 没有数据校验去重逻辑

---

### 4.7 `backend/api/agent.py`

这个文件不是接大模型 API，而是实现了一个“规则驱动的简易智能接口”。

它的特点是：

- 输入自然语言
- 用关键词和简单字符串规则解析意图
- 再去数据库做导入、搜索、统计

#### 1. 路由对象

```python
router = APIRouter(prefix="/agent", tags=["agent"])
```

说明所有接口都以 `/agent` 开头。

#### 2. 常量：`TOWN_LIST`

```python
TOWN_LIST = [...]
```

这里列出了项目支持识别的南海区镇街。

它的用途是：

- 在自然语言中识别用户提到的镇街
- 统一候选范围，避免无限自由文本

#### 3. 常量：`CATEGORY_KEYWORDS`

```python
CATEGORY_KEYWORDS = {
    "数据资源类": [...],
    "数据技术类": [...],
    ...
}
```

这是“类别关键词映射表”。

它定义了一个最简单的分类规则：

- 如果文本命中某类关键词，就归入对应分类

例如：

- 出现 `算法`、`AI`、`建模` 之类词时，更偏向“数据技术类”
- 出现 `数据中心`、`云平台` 时，更偏向“数据基础设施类”

这不是机器学习模型，而是规则匹配。

#### 4. `detect_category(text)`

这个函数完成类别识别。

核心逻辑：

1. 先把文本首尾空白去掉
2. 遍历每个分类和它的关键词列表
3. 只要某个关键词出现在文本中，就返回该分类
4. 如果都没命中，就返回“其他数据相关类”

这个函数的本质是：

- 优先命中
- 顺序敏感
- 粗粒度分类

它的优点是简单，缺点是容易误判，比如：

- “信息安全服务平台” 里同时可能触发多个词
- 先匹配到哪个类别，结果就归哪个

#### 5. `detect_town(text)`

这个函数做镇街识别。

逻辑是：

1. 遍历 `TOWN_LIST`
2. 如果某个镇街名称在文本中出现，就直接返回
3. 都没匹配到就返回 `"待补充"`

优点是稳定直观，缺点是只能识别固定写法，不支持别名或缩写。

#### 6. `detect_name(text)`

这个函数尝试从自然语言里抽取企业名称。

它不是 NLP 模型，而是基于规则：

- 优先找“叫XXX”
- 截断词包括：`，`、`,`、`在`、`主营`、`做`、`是`

例如：

```text
帮我加一家做智慧城市的公司，叫南海智联科技，在桂城街道
```

它会识别出：

```text
南海智联科技
```

如果文本里根本没有“叫”，它就返回：

```text
待命名企业
```

这说明这个函数对输入句式依赖比较强。

#### 7. `detect_products(text)`

这个函数尝试提取主营产品。

规则是：

- 如果出现“主营”，取“主营”后面的内容
- 否则如果出现“做”，取“做”后面的内容
- 遇到分隔符就截断
- 没识别到就返回 `"待补充"`

它本质上是为了让自然语言导入至少能粗略提取一个产品描述字段。

#### 8. `build_stats_summary(stats)`

这个函数把统计数字转成一句自然语言总结。

例如：

- 先构造分类到数量的映射
- 找出数量最多的类别
- 算占比
- 输出类似：

```text
数据技术类企业最多，共12家，占比约48.0%
```

所以 `/agent/stats` 不只是返回数字，还会返回一句总结。

#### 9. `agent_import()`

接口路径：

```text
/agent/import
```

它的目标是：让用户通过一句自然语言新增企业。

流程如下：

1. 从输入文本中提取 `name`、`town`、`category`、`products`
2. 查数据库看这个名字是否已经存在
3. 如果重名，就直接返回失败信息，不重复导入
4. 否则创建 `Enterprise` 对象
5. `category_reason` 自动写成“Agent 根据自然语言关键词自动判断为...”
6. `source_url` 固定写为 `"Agent输入"`
7. `evidence` 直接保存原始自然语言
8. `confidence` 设为 `0.75`
9. 提交数据库并返回结果

这个接口很适合演示“自然语言录入”，但它仍然是规则式，不是真正的 LLM Agent。

#### 10. `agent_search()`

接口路径：

```text
/agent/search
```

目标是让用户说一句自然语言，例如：

```text
帮我找南海区做数据安全的企业
```

接口会：

1. 解析类别
2. 解析镇街
3. 构造数据库查询
4. 最多返回 20 条结果

这里有一个设计细节：

```python
if category and category != "其他数据相关类":
```

它故意不把“其他数据相关类”作为强过滤条件。  
原因大概是：

- “其他数据相关类”很多时候其实只是“没识别出来”
- 如果把它当成硬条件，会把搜索结果限制得很奇怪

#### 11. `agent_stats()`

接口路径：

```text
/agent/stats
```

它先做一遍和 `/enterprises/stats` 类似的分类计数，再调用：

```python
summary = build_stats_summary(stats)
```

于是最终返回：

- `stats`：原始数字
- `summary`：一句自然语言总结

这个接口的意义在于让“智能体页面”或者“对话式问答”场景更自然。

#### 12. 这个文件的本质定位

这个文件更像是“规则引擎接口”，不是大模型系统。

它的优点：

- 不依赖外部 AI 服务
- 可离线运行
- 演示成本低

它的局限：

- 规则简单，句式依赖强
- 容易误判类别
- 名称提取鲁棒性不高
- 没有真正的语义理解

---

## 5. 前端代码详解

### 5.1 `frontend/src/main.jsx`

这是 React 应用入口文件。

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
```

这里完成了四件事：

- 导入 React 的严格模式
- 导入新的 React 挂载 API `createRoot`
- 导入全局 CSS
- 导入主组件 `App`

```jsx
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

这一段的含义是：

- 找到页面里的 `#root`
- 把 React 应用挂载进去
- 用 `StrictMode` 包裹主组件

`StrictMode` 在开发模式下会帮助发现潜在问题，比如不安全副作用。

---

### 5.2 `frontend/src/App.jsx`

这是整个前端最核心的文件，几乎所有页面逻辑都在里面。

#### 1. 组件库和依赖

```jsx
import {
  Card,
  Col,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
```

说明这个页面依赖：

- React 状态管理：`useState`, `useEffect`
- Ant Design：页面布局、表格、统计卡片、筛选器
- ECharts：分类统计柱状图

#### 2. 固定选项：分类和镇街

```jsx
const categoryOptions = [...]
const townOptions = [...]
```

这两个数组是下拉框选项。

好处是：

- 页面显示统一
- 避免用户自由输入带来的脏数据
- 和后端分类、镇街字段保持一致

#### 3. 组件状态

```jsx
const [selectedCategory, setSelectedCategory] = useState("全部");
const [selectedTown, setSelectedTown] = useState("全部");
const [keyword, setKeyword] = useState("");
const [tableData, setTableData] = useState([]);
const [loading, setLoading] = useState(false);
```

这几项分别控制：

- 当前选择的分类
- 当前选择的镇街
- 搜索关键词
- 表格数据
- 是否显示加载中

接着是统计状态：

```jsx
const [stats, setStats] = useState({
  total: 0,
  service: 0,
  tech: 0,
  security: 0,
  infrastructure: 0,
  other: 0,
});
```

这个状态用于存储后端 `/enterprises/stats` 返回的统计数据。

再往下是分页状态：

```jsx
const [pagination, setPagination] = useState({
  current: 1,
  pageSize: 5,
  total: 0,
});
```

分别表示：

- 当前页
- 每页条数
- 当前筛选结果总数量

#### 4. `fetchEnterprises()`

这是前端获取企业列表的核心函数。

参数默认值写法：

```jsx
({
  category = selectedCategory,
  town = selectedTown,
  page = pagination.current,
  pageSize = pagination.pageSize,
  keywordValue = keyword,
} = {})
```

它的含义是：

- 如果调用时没传参数，就自动用当前页面状态
- 如果传了，就优先用调用参数

##### 查询参数拼装

```jsx
const params = new URLSearchParams();
```

然后根据用户当前筛选条件逐步拼参数：

- 不是“全部”才传 `category`
- 不是“全部”才传 `town`
- 关键词不为空才传 `keyword`
- 分页参数 `page` 和 `page_size` 总是传

##### 调接口

```jsx
const url = `http://127.0.0.1:8000/enterprises/?${params.toString()}`;
const response = await fetch(url);
```

这会请求后端的企业列表接口。

##### 失败处理

```jsx
if (!response.ok) {
  throw new Error("获取企业数据失败");
}
```

如果 HTTP 状态码不是 2xx，就抛异常。

##### 数据格式转换

```jsx
const data = await response.json();
const items = Array.isArray(data.items) ? data.items : [];
```

后端返回的是分页对象，所以前端先取 `items`。

之后又映射成表格专用结构：

```jsx
const formattedData = items.map((item) => ({
  key: item.id,
  id: item.id,
  name: item.name || "",
  town: item.town || "",
  category: item.category || "",
  products: item.products || "",
}));
```

其中：

- `key` 是 Ant Design 表格要求的唯一键
- `|| ""` 是兜底，避免空值导致渲染不稳定

##### 更新分页

```jsx
setPagination((prev) => ({
  ...prev,
  current: data.page || 1,
  pageSize: data.page_size || 5,
  total: data.total || 0,
}));
```

说明分页信息最终以“后端返回值”为准，而不是只靠前端自己记。

#### 5. `fetchStats()`

这个函数单独请求：

```text
http://127.0.0.1:8000/enterprises/stats
```

拿到后端统计数据后：

```jsx
setStats(data);
```

也就是说，顶部卡片和图表的数据都来自后端，而不是前端自己计算当前页数据。

这很重要，因为它代表：

- 统计值是全量数据库统计
- 不受当前页分页影响

#### 6. `useEffect()`

```jsx
useEffect(() => {
  fetchEnterprises(...);
  fetchStats();
}, [selectedCategory, selectedTown]);
```

意思是：

- 页面初次加载时执行一次
- 当分类或镇街变化时重新执行

它会同时刷新：

- 表格数据
- 统计数据

这里没有把 `keyword` 放进依赖数组，所以关键词搜索不会自动触发，需要用户主动点搜索按钮。

#### 7. 表格列定义 `columns`

这部分告诉 Ant Design 表格怎么展示字段。

每一列包括：

- 标题
- 对应字段
- 唯一 key

其中分类列用了：

```jsx
render: (value) => <Tag>{value}</Tag>
```

这样分类会被包成标签显示，比纯文本更醒目。

#### 8. 三张统计卡片的值

```jsx
const totalCount = stats.total;
const serviceCount = stats.service;
const techCount = stats.tech;
```

这说明页面顶部目前展示的是：

- 企业总数
- 数据服务类数量
- 数据技术类数量

而不是表格当前页的统计值。

#### 9. 事件函数

##### `handleTableChange`

当分页变化时，重新请求对应页数据。

##### `handleSearch`

当用户点击搜索时，从第一页开始重新查。

#### 10. `chartOption`

这是 ECharts 的配置对象。

核心结构：

- `title`：图表标题
- `tooltip`：鼠标悬浮提示
- `xAxis`：横轴分类
- `yAxis`：纵轴数值
- `series`：柱状图数据

数据直接来自：

```jsx
[
  stats.service,
  stats.tech,
  stats.security,
  stats.infrastructure,
  stats.other
]
```

这意味着图表完全依赖后端 `/enterprises/stats` 的返回。

#### 11. JSX 页面结构

页面从外到内是：

1. 整体背景容器
2. 中间主卡片
3. 标题说明区
4. 图表区
5. 三张统计卡片
6. 筛选和搜索区
7. 数据表格区

这个布局适合一个典型的数据驾驶舱首页。

#### 12. 这个文件的设计特点

优点：

- 结构清晰，所有逻辑集中在一个组件里，便于小项目理解
- 数据流简单：后端接口 -> 状态 -> 表格/卡片/图表
- 交互完整：筛选、分页、搜索、统计都有

限制：

- 所有逻辑都写在一个组件里，后续项目大了会变得难维护
- 接口地址写死在代码里，不利于部署
- `App.css` 里的模板样式基本没有被这个页面真正使用
- `fetchStats` 的格式缩进不统一，说明文件可能是多次手工拼接修改的

---

### 5.3 `frontend/src/App.css`

这个文件基本保留了 Vite 默认模板的样式结构。

里面包括：

- `.counter`
- `.hero`
- `#center`
- `#next-steps`
- `.ticks`

这些类名和当前 `App.jsx` 页面并不匹配，也就是说：

- 这个文件大概率是模板残留
- 当前业务页面基本没有直接用到这些类

所以它在项目当前版本中的定位是：

- 存在
- 但不是主要生效样式来源

从维护角度看，这属于“可清理文件”。

---

### 5.4 `frontend/src/index.css`

这个文件定义了全局样式变量和页面基础外观。

#### 1. `:root`

里面定义了很多 CSS 变量，例如：

- `--text`
- `--bg`
- `--border`
- `--accent`

这些变量本来是为了支持统一主题色和布局风格。

#### 2. 深色模式

```css
@media (prefers-color-scheme: dark) {
  :root {
    ...
  }
}
```

说明模板原本支持深色模式切换。

#### 3. `#root`

```css
#root {
  width: 1126px;
  max-width: 100%;
  margin: 0 auto;
  ...
}
```

这会限制 React 根容器最大宽度，并加上边框与居中布局。

但当前 `App.jsx` 内部又写了自己的卡片容器，所以这份 CSS 是“全局兜底样式 + 模板遗留样式”的混合体。

#### 4. 结论

这个文件并非专门为当前业务页面重写，而是沿用了 Vite 模板的全局风格。

---

## 6. 前端配置文件详解

### 6.1 `frontend/package.json`

这个文件定义前端项目元信息、脚本和依赖。

#### 1. 基本信息

```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module"
}
```

- `private: true` 表示这个包不打算发布到 npm
- `type: "module"` 说明 Node 侧配置文件采用 ES Module 写法

#### 2. 脚本

```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "lint": "eslint .",
  "preview": "vite preview"
}
```

含义分别是：

- `npm run dev`：启动开发服务器
- `npm run build`：构建生产包
- `npm run lint`：运行 ESLint 检查
- `npm run preview`：本地预览构建结果

#### 3. 业务依赖

- `antd`
  UI 组件库
- `echarts`
  图表引擎
- `echarts-for-react`
  React 版 ECharts 封装
- `react`
  React 核心库
- `react-dom`
  React DOM 渲染
- `tslib`
  一些编译辅助运行时库

#### 4. 开发依赖

包括：

- Vite
- ESLint
- React hooks 相关 ESLint 插件
- React Vite 插件

这些都属于标准 React + Vite 工程依赖。

---

### 6.2 `frontend/vite.config.js`

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
```

这是一个非常标准的 Vite 配置。

含义是：

- 启用 React 插件
- 没有额外代理、别名、环境定制

这也解释了为什么前端代码里直接把后端地址写成了完整 URL，而不是通过 Vite 代理转发。

---

### 6.3 `frontend/eslint.config.js`

这个文件配置代码检查规则。

#### 1. 导入默认规则集和插件

- `@eslint/js`：基础 JS 规则
- `globals`：浏览器全局变量
- `eslint-plugin-react-hooks`：检查 hooks 用法
- `eslint-plugin-react-refresh`：配合 Vite 热更新

#### 2. 忽略目录

```js
globalIgnores(['dist'])
```

说明构建产物目录 `dist` 不参与 lint。

#### 3. 适用文件

```js
files: ['**/*.{js,jsx}']
```

只检查 JS 和 JSX 文件。

#### 4. 语言选项

启用了：

- ES 模块
- JSX
- 浏览器全局对象

#### 5. 自定义规则

```js
'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }]
```

意思是：

- 未使用变量默认报错
- 但如果变量名是大写或以下划线开头，可以忽略

这通常是为了兼容某些常量、占位变量或约定式命名。

---

### 6.4 `frontend/index.html`

这是 Vite 开发和构建时的 HTML 模板。

主要内容：

- 指定字符编码 `UTF-8`
- 设置 favicon
- 设置移动端 viewport
- 页面标题 `frontend`
- 页面中提供一个 `<div id="root"></div>`
- 用模块脚本加载 `/src/main.jsx`

这里的关键点是：

- React 不直接写 HTML 内容
- 它只需要一个根节点 `root`
- 真正页面内容都是 `main.jsx` 挂进去的

---

### 6.5 `frontend/README.md`

这是 Vite 默认模板 README，基本是脚手架自带内容。

它介绍了：

- React + Vite 的默认配置
- 可选编译器插件
- ESLint 扩展建议

它不是这个项目业务逻辑的一部分。

---

## 7. 数据采集与导入脚本详解

### 7.1 `scripts/amap_poi_source.py`

这个脚本的目标是：

- 调用高德 POI 搜索 API
- 按关键词抓取企业候选信息
- 自动猜一个类别
- 写入 `data/amap_enterprises.csv`

#### 1. 环境变量读取

```python
AMAP_KEY = os.getenv("AMAP_WEB_KEY", "").strip()
```

说明高德 API Key 不写死在代码里，而是从环境变量读取。

这是比较好的做法，因为：

- 避免把密钥提交到 Git
- 便于不同机器单独配置

#### 2. 区域限定

```python
TARGET_CITY = "440605"
CITY_LIMIT = "true"
```

这里使用高德的行政区编码限制搜索范围，目标是南海区。

这样做比直接传中文城市名更稳定，因为：

- 行政编码更精确
- 不容易模糊匹配到其他地区

#### 3. 输出路径

```python
OUTPUT_PATH = Path("data/amap_enterprises.csv")
```

说明生成的候选数据默认输出到 `data/` 目录。

#### 4. 搜索关键词 `KEYWORDS`

脚本会用一组关键词逐个去高德搜索，例如：

- 大数据
- 数据服务
- 数据安全
- 工业互联网
- 智慧城市
- 云平台
- 软件开发

这个设计思路是“宽撒网”：

- 不只搜一个词
- 而是用多组和数据产业相关的关键词去收集候选企业

#### 5. `fetch_poi_by_keyword()`

这是最核心的采集函数。

它会：

1. 按关键词请求高德接口
2. 分页抓取结果
3. 每页把 POI 数据加入结果列表
4. 请求间稍作休眠，避免过快访问

细节包括：

- `max_pages=3`
  每个关键词最多抓 3 页
- `offset=20`
  每页取 20 条

理论上一个关键词最多抓约 60 条。

#### 6. `guess_category()`

这个函数根据：

- 企业名
- POI 类型
- 搜索关键词

拼成一个文本，再按关键词判断大类。

示例逻辑：

- 出现“安全”相关词 -> 数据安全类
- 出现“云平台”/“机房” -> 数据基础设施类
- 出现“AI”/“算法”/“平台” -> 数据技术类
- 出现“智慧城市”/“信息服务” -> 数据服务类
- 都不满足 -> 其他数据相关类

这和 `agent.py` 里的分类思想是一致的，都是规则匹配。

#### 7. `build_rows()`

这个函数把高德返回的 POI 数据整理成 CSV 行。

流程是：

1. 遍历每个关键词
2. 获取对应 POI 列表
3. 提取 `name`、`address`、`type`、`location`
4. 用 `seen` 集合按企业名称去重
5. 调用 `guess_category()` 猜分类
6. 构造标准化的项目字段

这里构造出的字段已经和数据库表设计对齐了：

- 企业名称
- 所在镇街
- 主要类型
- 分类依据
- 主营产品
- 数据来源
- 证据片段
- 置信度
- 是否人工复核

这说明 CSV 不是随便存，而是作为“数据库导入中间格式”设计的。

#### 8. `save_csv()`

这个函数负责把整理好的行写成 CSV。

它先确保目录存在：

```python
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
```

再按固定字段顺序写出。

使用 `utf-8-sig` 编码的原因通常是：

- 方便 Excel 正常识别中文表头

#### 9. `main()`

主流程很简单：

1. 检查是否配置了高德 Key
2. 调用 `build_rows()`
3. 调用 `save_csv()`

这意味着这个脚本是一个“独立运行型采集程序”。

---

### 7.2 `scripts/import_csv.py`

这个脚本负责把 CSV 导入数据库。

它是采集和后端之间的桥梁。

#### 1. 修改模块搜索路径

```python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
```

因为脚本在 `scripts/` 目录中运行，而要导入 `backend` 包。  
所以这里手动把项目根目录加到 Python 模块搜索路径中。

这是一种简单但有效的脚本式写法。

#### 2. `CSV_PATH`

```python
CSV_PATH = Path("data/amap_enterprises.csv")
```

默认读取高德脚本生成的候选数据。

#### 3. `safe_str()`

用途：

- 从 CSV 行里安全读取指定字段
- 如果字段不存在或为 `None`，返回空字符串
- 最后再做 `strip()`

这样可以避免脏数据导致异常。

#### 4. `safe_lower()`

安全做字符串小写化。

用在布尔解析里。

#### 5. `parse_bool()`

它把多种文本写法转换成布尔值。

例如：

- `true`
- `1`
- `yes`
- `是`

都会被识别成 `True`。

#### 6. `normalize_name()`

这个函数是导入去重的关键。

它做了几件事：

1. 去掉首尾空白
2. 去掉括号内内容
3. 去掉所有空格
4. 转成小写

这样可以把这些名字视为同一个企业：

- `南海数据科技有限公司`
- `南海数据科技有限公司（佛山）`
- ` 南海 数据科技有限公司 `

这能有效减少因为格式差异带来的重复导入。

#### 7. `main()`

主逻辑如下：

##### 检查 CSV 文件

如果找不到目标文件，就直接提示并结束。

##### 建立数据库会话

```python
db = SessionLocal()
```

##### 先读已有企业名

```python
existing_names = {
    normalize_name(item.name): item.id
    for item in db.query(Enterprise).all()
}
```

这一步的目的是提前建立一个“已存在企业名索引”，用于快速判断重复。

##### 逐行读取 CSV

对每一行读取这些字段：

- 企业名称
- 所在镇街
- 主要类型
- 分类依据
- 主营产品
- 数据来源
- 证据片段
- 置信度
- 是否人工复核

##### 数据合法性检查

如果企业名称为空，直接跳过。

如果置信度不能转成浮点数，也跳过。

##### 重复检查

这里实际上做了两轮重复判断：

第一轮：

```python
if normalized in existing_names:
```

用预构建字典快速判断。

第二轮：

```python
existing = db.query(Enterprise).all()
for item in existing:
    if normalize_name(item.name) == normalized_name:
        ...
```

这会再次从数据库拉全表检查一次。

从功能上说，它确实更保险；但从性能和代码结构看，这一轮其实有些重复。

##### 写入数据库

通过 ORM 创建 `Enterprise` 对象后：

```python
db.add(enterprise)
db.flush()
```

这里先 `flush()` 而不是立即 `commit()`，好处是：

- 数据还在同一事务里
- 但已经可以拿到新插入记录的 `id`

最后统一：

```python
db.commit()
```

##### 异常处理

如果中间出错：

```python
db.rollback()
```

这样不会留下半成功半失败的数据状态。

#### 8. 这个脚本的特点

优点：

- 兼顾清洗和导入
- 去重思路比较实用
- 能处理 CSV 中常见格式问题

不足：

- `import re` 重复写了一次
- 第二轮全表重复检查开销偏大
- 没有把跳过原因保存成报告文件

---

## 8. 关键非代码文件说明

### 8.1 `README.md`

当前项目根目录 README 只有一句标题：

```md
# nanhai-data-map
```

说明项目总说明还没完善。

### 8.2 `requirements.txt`

当前为空文件。

这说明后端 Python 依赖尚未系统整理到这个文件里。

### 8.3 `data/amap_enterprises.csv`

这是高德脚本抓取并整理出的候选企业数据。

它是“数据采集结果 + 导入中间文件”。

### 8.4 `data/sample_20.csv`

这是示例数据文件，通常用于：

- 演示
- 测试导入
- 前期联调

### 8.5 `enterprise.db`

这是 SQLite 实际数据库文件。

它存放所有最终导入成功的企业记录。

### 8.6 `docs/*.md`

这些文档包括：

- `taxonomy.md`
- `agent_design.md`
- `real_data_source.md`
- `data_cleaning_notes.md`
- `backend-guide.md`

它们不属于运行时代码，但属于项目设计说明和数据标准说明。

其中最重要的是 `taxonomy.md`，因为它决定了“企业主要类型”字段的分类标准。

### 8.7 `docs/screenshots/`

这里是页面截图和接口截图，作用是项目展示，不是运行逻辑。

### 8.8 `frontend/public/` 与 `frontend/src/assets/`

这些是静态资源文件，比如图标、图片。

它们是界面资源，不是程序逻辑代码。

### 8.9 `.git/`

Git 仓库元数据，用于版本控制，不是项目业务代码。

### 8.10 `node_modules/`

第三方依赖目录，是 npm 安装得到的库文件，不是这个项目自己写的源码。

### 8.11 `__pycache__/`

Python 解释器自动生成的字节码缓存目录，不属于手写源码。

---

## 9. 项目数据流总解释

这个项目的完整数据流如下：

### 1. 候选企业采集

`scripts/amap_poi_source.py`

作用：

- 用高德关键词搜索南海区企业
- 生成初步候选 CSV

输出：

- `data/amap_enterprises.csv`

### 2. 数据清洗与导入

`scripts/import_csv.py`

作用：

- 读取 CSV
- 做名称标准化和去重
- 转成 `Enterprise` 对象
- 写入 SQLite

输出：

- `enterprise.db`

### 3. 后端对外服务

`backend/`

作用：

- 提供新增企业接口
- 提供分页、筛选、搜索接口
- 提供分类统计接口
- 提供简易自然语言 agent 接口

### 4. 前端展示

`frontend/src/App.jsx`

作用：

- 拉取企业列表
- 拉取统计数据
- 展示图表、统计卡片和表格
- 支持筛选、搜索、分页

---

## 10. 项目的优点

这个项目有几个很明显的优点：

1. 结构完整，具备采集、导入、存储、查询、展示全链路
2. 技术选型轻量，适合课程项目和演示
3. 数据表设计考虑了分类依据和证据追溯
4. 前后端联动路径清晰
5. 额外加入了一个规则式 agent，增强了展示效果

---

## 11. 项目的主要问题与改进方向

从代码质量和工程化角度看，目前还有这些明显问题：

1. `requirements.txt` 为空，后端依赖没有沉淀
2. 根目录 README 几乎没有内容
3. 前端保留了不少模板残留样式文件
4. 前端接口地址写死，部署不够灵活
5. `agent.py` 和采集脚本中的分类逻辑是规则匹配，容易误判
6. `import_csv.py` 有重复导入检查逻辑，结构还能再优化
7. 后端统计接口是逐类多次查询，后续可以改成聚合统计
8. 没有用户权限、更新删除、批量导入 API 等更完整的后台能力

---

## 12. 一句话总结

`nanhai-data-map` 是一个围绕“南海区数据产业企业图谱”构建的全栈原型系统：  
脚本负责采集和导入数据，FastAPI 负责提供企业数据与统计接口，React 前端负责把这些数据做成筛选、搜索、表格和图表展示，同时还额外提供了一个基于规则的简易“agent”能力。
