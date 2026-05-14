import { CloudUploadOutlined, DatabaseOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  message,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography
} from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useRef, useState } from "react";
import "./App.css";

const { Title, Paragraph, Text } = Typography;

const categoryOptions = [
  { label: "全部类型", value: "全部" },
  { label: "数据资源", value: "数据资源" },
  { label: "数据技术", value: "数据技术" },
  { label: "数据服务", value: "数据服务" },
  { label: "数据应用", value: "数据应用" },
  { label: "数据安全", value: "数据安全" },
  { label: "数据基础设施", value: "数据基础设施" },
];

const townOptions = [
  { label: "全部镇街", value: "全部" },
  { label: "桂城街道", value: "桂城街道" },
  { label: "狮山镇", value: "狮山镇" },
  { label: "大沥镇", value: "大沥镇" },
  { label: "里水镇", value: "里水镇" },
  { label: "丹灶镇", value: "丹灶镇" },
  { label: "西樵镇", value: "西樵镇" },
  { label: "九江镇", value: "九江镇" },
];

const exampleInstructions = [
  "采集桂城街道的数据安全企业",
  "帮我找狮山镇的数据技术公司",
  "采集大沥镇的数据服务企业",
  "找桂城街道的数据基础设施类",
];

function App() {
  const [queryText, setQueryText] = useState("");
  const [filterKeyword, setFilterKeyword] = useState("");
  const [filterCategory, setFilterCategory] = useState("全部");
  const [filterTown, setFilterTown] = useState("全部");
  const [tableData, setTableData] = useState([]);
  const [queryResults, setQueryResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [queryLoading, setQueryLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [querySummary, setQuerySummary] = useState(null);
  const [queryMeta, setQueryMeta] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [graphData, setGraphData] = useState(null);
  const [insightMap, setInsightMap] = useState({});
  const [collecting, setCollecting] = useState(false);
  const [approving, setApproving] = useState(false);
  const [collectResult, setCollectResult] = useState(null);
  const [collectCandidates, setCollectCandidates] = useState([]);
  const [selectedCandidateKeys, setSelectedCandidateKeys] = useState([]);
  const [collectInstruction, setCollectInstruction] = useState("采集桂城街道的数据安全企业");
  const recognitionRef = useRef(null);

  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });

  const formatItems = (items) =>
    (Array.isArray(items) ? items : []).map((item) => ({
      key: item.id,
      ...item,
    }));

  const fetchStats = async () => {
    try {
      const response = await fetch("/api/enterprises/stats");
      if (!response.ok) throw new Error("获取统计信息失败");
      const data = await response.json();
      setStats(data);
    } catch (error) {
      message.error(error.message || "统计信息加载失败");
    }
  };

  const fetchGraphData = async () => {
    try {
      const response = await fetch("/api/enterprises/graph/network");
      if (!response.ok) throw new Error("获取知识图谱失败");
      const data = await response.json();
      setGraphData(data);
    } catch (error) {
      message.error(error.message || "知识图谱加载失败");
    }
  };

  const runSmartCollect = async () => {
    if (!collectInstruction.trim()) {
      message.warning("请输入采集指令");
      return;
    }

    setCollecting(true);
    setCollectResult(null);
    setCollectCandidates([]);
    setSelectedCandidateKeys([]);
    try {
      const params = new URLSearchParams({ instruction: collectInstruction });
      const response = await fetch(`/api/enterprises/collect/smart?${params.toString()}`, {
        method: "POST",
      });
      const data = await response.json();
      setCollectResult(data);
      const candidates = (data.candidates || []).map((item, index) => ({
        ...item,
        key: item.key || `${item.name}-${index}`,
      }));
      setCollectCandidates(candidates);
      setSelectedCandidateKeys(candidates.map(item => item.key));
      if (data.success) {
        message.success(data.message);
      } else {
        message.error(data.message || "采集失败");
      }
    } catch (error) {
      message.error("采集失败：" + error.message);
    } finally {
      setCollecting(false);
    }
  };

  const approveCollectCandidates = async () => {
    const selectedCandidates = collectCandidates.filter(item => selectedCandidateKeys.includes(item.key));
    if (!selectedCandidates.length) {
      message.warning("请先选择要入库的候选企业");
      return;
    }

    setApproving(true);
    try {
      const response = await fetch("/api/enterprises/collect/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          batch_id: collectResult?.batch_id,
          candidates: selectedCandidates,
        }),
      });
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "入库失败");
      }
      message.success(data.message);
      setCollectResult(prev => ({ ...(prev || {}), approveResult: data }));
      setCollectCandidates([]);
      setSelectedCandidateKeys([]);
      await Promise.all([fetchStats(), fetchEnterprises(), fetchGraphData()]);
    } catch (error) {
      message.error(error.message || "入库失败");
    } finally {
      setApproving(false);
    }
  };

  const fetchEnterprises = async ({
    category = filterCategory,
    town = filterTown,
    page = 1,
    pageSize = pagination.pageSize,
    keywordValue = filterKeyword,
  } = {}) => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (category !== "全部") params.append("category", category);
      if (town !== "全部") params.append("town", town);
      if (keywordValue.trim()) params.append("keyword", keywordValue.trim());

      const response = await fetch(`/api/enterprises/?${params.toString()}`);
      if (!response.ok) throw new Error("获取企业列表失败");
      const data = await response.json();
      setTableData(formatItems(data.items));
      setPagination({
        current: data.page || 1,
        pageSize: data.page_size || pageSize,
        total: data.total || 0,
      });
    } catch (error) {
      message.error(error.message || "加载企业列表失败");
    } finally {
      setLoading(false);
    }
  };

  const runNaturalLanguageQuery = async (text) => {
    const cleanText = text.trim();
    if (!cleanText) {
      message.warning("请输入查询内容");
      return;
    }
    try {
      setQueryLoading(true);
      const params = new URLSearchParams({ text: cleanText, page: "1", page_size: "20" });
      const response = await fetch(`/api/enterprises/query?${params.toString()}`);
      if (!response.ok) throw new Error("查询失败");
      const data = await response.json();
      setQuerySummary(data.parsed);
      setQueryMeta({ input: data.input, total: data.total });
      setQueryText(cleanText);
      setQueryResults(formatItems(data.items));
    } catch (error) {
      message.error(error.message || "查询失败");
    } finally {
      setQueryLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchEnterprises();
    fetchGraphData();
  }, []);

  const fetchEnterpriseInsight = async (enterpriseId) => {
    if (insightMap[enterpriseId]) return;
    try {
      const response = await fetch(`/api/enterprises/${enterpriseId}/insight`);
      if (!response.ok) throw new Error("获取企业画像失败");
      const data = await response.json();
      if (data.success) {
        setInsightMap((prev) => ({ ...prev, [enterpriseId]: data.insight }));
      }
    } catch (error) {
      message.error(error.message || "获取企业画像失败");
    }
  };

  const handleTableChange = (newPagination) => {
    fetchEnterprises({
      category: filterCategory,
      town: filterTown,
      page: newPagination.current,
      pageSize: newPagination.pageSize,
      keywordValue: filterKeyword,
    });
  };

  const handleFilterSearch = () => {
    fetchEnterprises({ page: 1 });
  };

  const handleVoiceSearch = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      message.warning("当前浏览器不支持语音识别");
      return;
    }
    if (!recognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.lang = "zh-CN";
      recognition.interimResults = false;
      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => {
        setIsListening(false);
        message.error("语音识别失败");
      };
      recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript?.trim() || "";
        if (!transcript) {
          message.warning("没有识别到有效内容");
          return;
        }
        setQueryText(transcript);
        runNaturalLanguageQuery(transcript);
      };
      recognitionRef.current = recognition;
    }
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
    }
  };

  const columns = [
    { title: "企业名", dataIndex: "name", key: "name", width: 240, fixed: "left" },
    { title: "所在镇街", dataIndex: "town", key: "town", width: 150, render: (v) => <Tag color="blue">{v}</Tag> },
    { title: "主要类型", dataIndex: "category", key: "category", width: 160, render: (v) => <Tag color="gold">{v}</Tag> },
    { title: "分类依据", dataIndex: "category_reason", key: "category_reason", width: 360, ellipsis: true },
    { title: "主营产品", dataIndex: "products", key: "products", width: 300, ellipsis: true },
    { title: "可信度", dataIndex: "confidence_level", key: "confidence_level", width: 120, render: (v) => <Tag color={v === "高" ? "green" : v === "中" ? "gold" : "default"}>{v}</Tag> },
    { title: "产业链位置", dataIndex: "chain_position", key: "chain_position", width: 120 },
  ];

  const collectCandidateColumns = [
    { title: "候选企业", dataIndex: "name", key: "name", width: 240 },
    { title: "镇街", dataIndex: "town", key: "town", width: 120, render: (v) => <Tag color="blue">{v}</Tag> },
    { title: "建议类型", dataIndex: "category", key: "category", width: 140, render: (v) => <Tag color="gold">{v}</Tag> },
    { title: "主营产品", dataIndex: "products", key: "products", width: 220, ellipsis: true },
    { title: "分类依据", dataIndex: "category_reason", key: "category_reason", width: 320, ellipsis: true },
    { title: "来源", dataIndex: "data_source", key: "data_source", width: 130 },
    { title: "置信度", dataIndex: "confidence", key: "confidence", width: 100 },
  ];

  const graphNodeCount = graphData?.nodes?.length || 0;
  const graphLinkCount = graphData?.links?.length || 0;
  const graphHeight = Math.min(860, Math.max(460, 360 + graphNodeCount * 3 + graphLinkCount * 0.35));

  const graphOption = {
    color: ["#2f6fed", "#d97b16", "#2f9e75"],
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        if (params.dataType === "edge") {
          return `关系：${params.data.value || "关联"}`;
        }
        return params.data?.name || "";
      },
    },
    legend: {
      top: 0,
      left: "center",
      textStyle: { color: "#43566f" },
    },
    series: [{
      type: "graph", layout: "force", roam: true, draggable: true,
      data: graphData?.nodes || [], links: graphData?.links || [],
      categories: graphData?.categories || [],
      edgeSymbol: ["none", "arrow"],
      edgeSymbolSize: 8,
      edgeLabel: { show: true, formatter: "{c}", fontSize: 10, color: "#6b7788" },
      label: { show: true, position: "right", color: "#17304f", fontSize: 11 },
      lineStyle: { color: "source", curveness: 0.08, opacity: 0.72 },
      force: { repulsion: 220, edgeLength: 120, gravity: 0.08 },
      emphasis: { focus: "adjacency", lineStyle: { width: 3 } },
    }],
  };

  const expandedRowRender = (record) => {
    const insight = insightMap[record.id];
    return (
      <div className="insight-panel">
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={10}>
            <Card size="small" title="企业画像">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="企业规模">{record.company_size}</Descriptions.Item>
                <Descriptions.Item label="可信度">{record.confidence_level}</Descriptions.Item>
                <Descriptions.Item label="产业链位置">{record.chain_position}</Descriptions.Item>
                <Descriptions.Item label="多源佐证">{record.source_count} 个来源</Descriptions.Item>
              </Descriptions>
              <div className="tag-block">{(record.profile_tags || []).map(tag => <Tag key={tag} color="blue">{tag}</Tag>)}</div>
            </Card>
          </Col>
          <Col xs={24} xl={14}>
            <Card size="small" title="证据展示">
              <p className="insight-text">{record.evidence_summary}</p>
              <div className="tag-block">{(record.data_sources || []).map(s => <Tag key={s} color="gold">{s}</Tag>)}</div>
              {(record.source_links || []).length > 0 && (
                <div className="evidence-links">{(record.source_links || []).map(link => <a key={link} href={link} target="_blank" rel="noreferrer">{link}</a>)}</div>
              )}
            </Card>
          </Col>
          <Col xs={24} xl={12}>
            <Card size="small" title="上下游 / 关联企业">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="上游企业">{insight?.upstream_enterprises?.join("、") || "暂无"}</Descriptions.Item>
                <Descriptions.Item label="下游企业">{insight?.downstream_enterprises?.join("、") || "暂无"}</Descriptions.Item>
                <Descriptions.Item label="关联企业">{insight?.related_enterprises?.join("、") || "暂无"}</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
        </Row>
      </div>
    );
  };

  return (
    <div className="page-shell">
      <div className="page-content">
        {/* 头部区域 */}
        <section className="hero-panel">
          <div>
            <Text className="eyebrow">NANHAI DATA MAP</Text>
            <Title style={{ marginTop: 60 }}>南海区数据产业图谱查询系统</Title>
          </div>
          <div className="hero-metrics">
            <Card className="metric-card">
              <Statistic title="当前已入库企业" value={stats?.total || 0} suffix={`/ ${stats?.target || 1000}`} />
            </Card>
            <Card className="metric-card">
              <Statistic title="覆盖镇街" value={Object.values(stats?.town_stats || {}).filter(Boolean).length} suffix="/ 7" />
            </Card>
          </div>
        </section>

        {/* 统计卡片 */}
        <Row gutter={[16, 16]} className="stats-grid">
          {categoryOptions.filter(item => item.value !== "全部").map(item => (
            <Col xs={12} md={8} xl={4} key={item.value}>
              <Card className="stats-card">
                <Statistic title={item.label} value={stats?.category_stats?.[item.value] || 0} />
              </Card>
            </Col>
          ))}
        </Row>

        {/* 知识图谱展示 */}
        <Card className="graph-card">
          <div className="section-heading">
            <div>
              <Title level={4}>南海区数据产业知识图谱</Title>
              <Paragraph>
                展示企业、所在镇街、产业类型及关联企业关系，可拖拽节点、滚轮缩放查看产业连接。
              </Paragraph>
            </div>
            <Space wrap>
              <Tag color="blue">{graphNodeCount} 个节点</Tag>
              <Tag color="gold">{graphLinkCount} 条关系</Tag>
            </Space>
          </div>
          <ReactECharts
            option={graphOption}
            className="knowledge-graph"
            style={{ height: graphHeight }}
            notMerge
            lazyUpdate
            showLoading={!graphData}
          />
        </Card>

        {/* 智能采集模块 - 仅 ENScan_GO */}
        <Card className="collect-card" style={{ marginBottom: 20, background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" }}>
          <div style={{ color: "white", marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: "bold", marginBottom: 8 }}>
              <CloudUploadOutlined style={{ marginRight: 8 }} /> 智能采集
            </div>
            <div style={{ fontSize: 13, opacity: 0.8 }}>
              基于天眼查 API 采集真实企业工商信息
            </div>
          </div>

          {/* 单行输入框 */}
          <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
            <Input
              size="large"
              placeholder="例如：采集桂城街道的数据安全企业"
              value={collectInstruction}
              onChange={e => setCollectInstruction(e.target.value)}
              onPressEnter={runSmartCollect}
              style={{ background: "rgba(255,255,255,0.95)", borderRadius: 12, flex: 1 }}
              allowClear
            />
            <Button
              type="primary"
              size="large"
              icon={<DatabaseOutlined />}
              loading={collecting}
              onClick={runSmartCollect}
              style={{ background: "#fff", color: "#667eea", border: "none", borderRadius: 12 }}
            >
              {collecting ? "采集中..." : "开始采集"}
            </Button>
          </div>

          {/* 示例指令 */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {exampleInstructions.map(inst => (
              <Button
                key={inst}
                size="small"
                onClick={() => setCollectInstruction(inst)}
                style={{ background: "rgba(255,255,255,0.2)", color: "white", border: "none" }}
              >
                {inst}
              </Button>
            ))}
          </div>

          {/* 采集结果展示 */}
          {collectResult && collectResult.success && (
            <div style={{ marginTop: 12, padding: 12, background: "rgba(255,255,255,0.2)", borderRadius: 12 }}>
              <Space direction="vertical" size={4} style={{ width: "100%", color: "white" }}>
                <Text style={{ color: "white" }}>✅ {collectResult.message}</Text>
                <Text style={{ color: "white", fontSize: 12 }}>
                  解析结果：镇街 {collectResult.parsed?.town || "未指定"} |
                  类型 {collectResult.parsed?.category || "未指定"} |
                  关键词 {collectResult.parsed?.keyword || "默认"}
                </Text>
                <Text style={{ color: "white", fontSize: 12 }}>
                  批次: {collectResult.batch_id} |
                  候选: {collectResult.candidate_count || collectCandidates.length}家 |
                  已选: {selectedCandidateKeys.length}家
                </Text>
                {(collectResult.source_results || []).length > 0 && (
                  <Text style={{ color: "#d7e4ff", fontSize: 12 }}>
                    数据源：ENScan_GO / 天眼查
                  </Text>
                )}
                {collectResult.approveResult && (
                  <Text style={{ color: "#b8f5cf", fontSize: 12 }}>
                    {collectResult.approveResult.message}
                  </Text>
                )}
              </Space>
            </div>
          )}
          {collectResult && !collectResult.success && (
            <div style={{ marginTop: 12, padding: 12, background: "rgba(255,255,255,0.18)", borderRadius: 12 }}>
              <Space direction="vertical" size={4} style={{ width: "100%", color: "white" }}>
                <Text style={{ color: "white" }}>未采集到数据：{collectResult.message}</Text>
                <Text style={{ color: "white", fontSize: 12 }}>
                  解析结果：镇街 {collectResult.parsed?.town || "未指定"} |
                  类型 {collectResult.parsed?.category || "未指定"} |
                  关键词 {collectResult.parsed?.keyword || "默认"}
                </Text>
              </Space>
            </div>
          )}

          {collectCandidates.length > 0 && (
            <div className="candidate-review-panel">
              <div className="candidate-review-header">
                <div>
                  <Text strong>待筛选候选企业（ENScan_GO/天眼查）</Text>
                  <div className="candidate-review-meta">
                    已选 {selectedCandidateKeys.length} / {collectCandidates.length} 家，确认后才会写入正式数据库。
                  </div>
                </div>
                <Space wrap>
                  <Button size="small" onClick={() => setSelectedCandidateKeys(collectCandidates.map(item => item.key))}>
                    全选
                  </Button>
                  <Button size="small" onClick={() => setSelectedCandidateKeys([])}>
                    清空
                  </Button>
                  <Button
                    type="primary"
                    loading={approving}
                    disabled={!selectedCandidateKeys.length}
                    onClick={approveCollectCandidates}
                  >
                    确认入库
                  </Button>
                </Space>
              </div>
              <Table
                columns={collectCandidateColumns}
                dataSource={collectCandidates}
                rowKey="key"
                size="small"
                pagination={{ pageSize: 8, showSizeChanger: false }}
                scroll={{ x: 1250 }}
                rowSelection={{
                  selectedRowKeys: selectedCandidateKeys,
                  onChange: keys => setSelectedCandidateKeys(keys),
                }}
              />
            </div>
          )}
        </Card>

        {/* 查询模块 */}
        <Card className="query-card">
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <div>
              <Title level={4}>文字 / 语音查询</Title>
              <Paragraph>可以直接输入"查找桂城街道的数据服务企业"这类自然语言，也可以点击语音按钮进行口述查询。</Paragraph>
            </div>
            <Space wrap>
              {["查找桂城街道的数据服务企业", "帮我找数据安全企业", "搜索狮山镇的企业"].map(query => (
                <Button key={query} onClick={() => { setQueryText(query); runNaturalLanguageQuery(query); }}>
                  {query}
                </Button>
              ))}
            </Space>
            <div className="query-toolbar">
              <Input
                size="large"
                value={queryText}
                allowClear
                placeholder="例如：帮我找桂城街道的数据技术企业"
                onChange={e => setQueryText(e.target.value)}
                onPressEnter={() => runNaturalLanguageQuery(queryText)}
              />
              <Button size="large" type="primary" onClick={() => runNaturalLanguageQuery(queryText)}>文字查询</Button>
              <Button size="large" className={isListening ? "listening-btn" : ""} onClick={handleVoiceSearch}>
                {isListening ? "停止录音" : "语音查询"}
              </Button>
            </div>
            {querySummary && (
              <Alert
                type="info"
                showIcon
                message="语义解析结果"
                description={
                  <>
                    <div>查询原文：{queryMeta?.input || queryText}</div>
                    <div>识别结果：类型 {querySummary.category || "未识别"}；镇街 {querySummary.town || "未识别"}；关键词 {querySummary.keyword || "无"}</div>
                    <div>命中企业：{queryMeta?.total ?? 0} 家</div>
                  </>
                }
              />
            )}
            {querySummary && (
              <Table columns={columns} dataSource={queryResults} loading={queryLoading} rowKey="id" pagination={false} scroll={{ x: 1300 }} size="middle" />
            )}
          </Space>
        </Card>

        {/* 筛选模块 */}
        <Card className="filter-card">
          <Space wrap size="middle">
            <Select value={filterCategory} options={categoryOptions} onChange={setFilterCategory} style={{ width: 180 }} />
            <Select value={filterTown} options={townOptions} onChange={setFilterTown} style={{ width: 180 }} />
            <Input.Search value={filterKeyword} placeholder="按企业名称关键词筛选" allowClear onChange={e => setFilterKeyword(e.target.value)} onSearch={handleFilterSearch} style={{ width: 320 }} />
            <Button onClick={handleFilterSearch}>按条件筛选</Button>
          </Space>
        </Card>

        {/* 企业列表 */}
        <Card className="table-card">
          <Table
            columns={columns}
            dataSource={tableData}
            loading={loading}
            rowKey="id"
            scroll={{ x: 1300 }}
            expandable={{ expandedRowRender, onExpand: (expanded, record) => expanded && fetchEnterpriseInsight(record.id) }}
            pagination={{ ...pagination, showSizeChanger: true, pageSizeOptions: ["10", "20", "50"], showTotal: total => `共 ${total} 条企业记录` }}
            onChange={handleTableChange}
          />
        </Card>
      </div>
    </div>
  );
}

export default App;