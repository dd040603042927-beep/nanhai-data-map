import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
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

const exampleQueries = [
  "查找桂城街道的数据服务企业",
  "帮我找数据安全企业",
  "搜索狮山镇的企业",
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
  const [platformOverview, setPlatformOverview] = useState(null);
  const [platformLog, setPlatformLog] = useState("");
  const [platformSummary, setPlatformSummary] = useState({
    collected_count: 0,
    imported_count: 0,
    merged_count: 0,
  });
  const [runningTaskId, setRunningTaskId] = useState("");
  const [platformInstruction, setPlatformInstruction] = useState("采集桂城街道的数据服务企业");
  const [graphData, setGraphData] = useState(null);
  const [insightMap, setInsightMap] = useState({});
  const recognitionRef = useRef(null);

  const [smartCollecting, setSmartCollecting] = useState(false);
  const [smartCollectResult, setSmartCollectResult] = useState(null);

  // 候选企业审核相关状态
  const [candidates, setCandidates] = useState([]);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);

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
      if (!response.ok) {
        throw new Error("获取统计信息失败");
      }

      const data = await response.json();
      setStats(data);
    } catch (error) {
      message.error(error.message || "统计信息加载失败");
    }
  };

  const fetchPlatformOverview = async () => {
    try {
      const response = await fetch("/api/enterprises/platform/overview");
      if (!response.ok) {
        throw new Error("获取平台概览失败");
      }

      const data = await response.json();
      setPlatformOverview(data);
    } catch (error) {
      message.error(error.message || "平台概览加载失败");
    }
  };

  const fetchGraphData = async () => {
    try {
      const response = await fetch("/api/enterprises/graph/network");
      if (!response.ok) {
        throw new Error("获取知识图谱失败");
      }

      const data = await response.json();
      setGraphData(data);
    } catch (error) {
      message.error(error.message || "知识图谱加载失败");
    }
  };

  // 获取候选企业列表
  const fetchCandidates = async () => {
    try {
      setCandidateLoading(true);
      const response = await fetch("/api/enterprises/candidates");
      if (!response.ok) throw new Error("获取候选列表失败");
      const data = await response.json();
      if (data.success) {
        setCandidates(data.items || []);
        setSelectedIds(data.items?.filter(item => item.selected).map(item => item.id) || []);
      }
    } catch (error) {
      message.error(error.message || "获取候选列表失败");
    } finally {
      setCandidateLoading(false);
    }
  };

  // 切换单个选中状态
  const toggleCandidate = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  // 全选/取消全选
  const toggleAll = () => {
    if (selectedIds.length === candidates.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(candidates.map(item => item.id));
    }
  };

  // 批量确认入库
  const approveCandidates = async () => {
    if (selectedIds.length === 0) {
      message.warning("请先选择要入库的企业");
      return;
    }
    try {
      const ids = selectedIds.join(",");
      const response = await fetch(`/api/enterprises/candidates/approve?ids=${ids}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("入库失败");
      const data = await response.json();
      message.success(`成功入库 ${data.approved_count} 家企业`);
      await fetchCandidates();
      await Promise.all([fetchStats(), fetchEnterprises(), fetchGraphData()]);
    } catch (error) {
      message.error(error.message || "入库失败");
    }
  };

  // 批量删除
  const rejectCandidates = async () => {
    if (selectedIds.length === 0) {
      message.warning("请先选择要删除的企业");
      return;
    }
    try {
      const ids = selectedIds.join(",");
      const response = await fetch(`/api/enterprises/candidates/reject?ids=${ids}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("删除失败");
      const data = await response.json();
      message.success(`已删除 ${data.rejected_count} 家企业`);
      await fetchCandidates();
      await Promise.all([fetchStats(), fetchEnterprises(), fetchGraphData()]);
    } catch (error) {
      message.error(error.message || "删除失败");
    }
  };

  const runPlatformTask = async (taskId) => {
    try {
      setRunningTaskId(taskId);
      const params = new URLSearchParams({
        task: taskId,
      });

      if (platformInstruction.trim()) {
        params.append("instruction", platformInstruction.trim());
      }

      const response = await fetch(`/api/enterprises/platform/run?${params.toString()}`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("平台任务执行失败");
      }

      const data = await response.json();
      setPlatformLog(data.output || "");
      setPlatformSummary(
        data.summary || {
          collected_count: 0,
          imported_count: 0,
          merged_count: 0,
        },
      );
      if (!data.success) {
        throw new Error(data.message || data.output || "平台任务执行失败");
      }

      message.success("平台任务执行完成");
      await Promise.all([
        fetchStats(),
        fetchEnterprises({
          category: filterCategory,
          town: filterTown,
          page: pagination.current,
          pageSize: pagination.pageSize,
          keywordValue: filterKeyword,
        }),
        fetchPlatformOverview(),
        fetchGraphData(),
      ]);
    } catch (error) {
      message.error(error.message || "平台任务执行失败");
    } finally {
      setRunningTaskId("");
    }
  };

  // 一键智能采集
  const runSmartCollect = async () => {
    const instruction = platformInstruction.trim();
    if (!instruction) {
      message.warning("请输入采集指令");
      return;
    }

    try {
      setSmartCollecting(true);
      setSmartCollectResult(null);

      const params = new URLSearchParams({
        instruction: instruction,
      });

      const response = await fetch(`/api/enterprises/smart-collect?${params.toString()}`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("智能采集失败");
      }

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "智能采集失败");
      }

      setSmartCollectResult(data);
      message.success(data.message || "智能采集完成");

      await fetchCandidates();
      await Promise.all([
        fetchStats(),
        fetchEnterprises({
          category: filterCategory,
          town: filterTown,
          page: pagination.current,
          pageSize: pagination.pageSize,
          keywordValue: filterKeyword,
        }),
        fetchPlatformOverview(),
        fetchGraphData(),
      ]);
    } catch (error) {
      message.error(error.message || "智能采集失败");
    } finally {
      setSmartCollecting(false);
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
      setQuerySummary(null);
      setQueryMeta(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });

      if (category !== "全部") {
        params.append("category", category);
      }
      if (town !== "全部") {
        params.append("town", town);
      }
      if (keywordValue.trim()) {
        params.append("keyword", keywordValue.trim());
      }

      const response = await fetch(`/api/enterprises/?${params.toString()}`);
      if (!response.ok) {
        throw new Error("获取企业列表失败");
      }

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
      message.warning("请输入查询内容后再执行文字查询");
      return;
    }

    try {
      setQueryLoading(true);

      const params = new URLSearchParams({
        text: cleanText,
        page: "1",
        page_size: "20",
      });

      const response = await fetch(`/api/enterprises/query?${params.toString()}`);
      if (!response.ok) {
        throw new Error("自然语言查询失败");
      }

      const data = await response.json();
      setQuerySummary(data.parsed);
      setQueryMeta({
        input: data.input,
        total: data.total,
      });
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
    fetchPlatformOverview();
    fetchGraphData();
    fetchCandidates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchEnterpriseInsight = async (enterpriseId) => {
    if (insightMap[enterpriseId]) {
      return;
    }

    try {
      const response = await fetch(`/api/enterprises/${enterpriseId}/insight`);
      if (!response.ok) {
        throw new Error("获取企业增强画像失败");
      }

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "企业增强画像获取失败");
      }

      setInsightMap((prev) => ({
        ...prev,
        [enterpriseId]: data.insight,
      }));
    } catch (error) {
      message.error(error.message || "企业增强画像获取失败");
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
    fetchEnterprises({
      category: filterCategory,
      town: filterTown,
      page: 1,
      pageSize: pagination.pageSize,
      keywordValue: filterKeyword,
    });
  };

  const handleVoiceSearch = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      message.warning("当前浏览器不支持语音识别，请改用文字查询");
      return;
    }

    if (!recognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.lang = "zh-CN";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => {
        setIsListening(false);
        message.error("语音识别失败，请重试");
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
      return;
    }

    recognitionRef.current.start();
  };

  const columns = [
    {
      title: "企业名",
      dataIndex: "name",
      key: "name",
      width: 240,
      fixed: "left",
    },
    {
      title: "所在镇街",
      dataIndex: "town",
      key: "town",
      width: 150,
      render: (value) => <Tag color="blue">{value}</Tag>,
    },
    {
      title: "主要类型",
      dataIndex: "category",
      key: "category",
      width: 160,
      render: (value) => <Tag color="gold">{value}</Tag>,
    },
    {
      title: "分类依据",
      dataIndex: "category_reason",
      key: "category_reason",
      width: 360,
      ellipsis: true,
    },
    {
      title: "主营产品",
      dataIndex: "products",
      key: "products",
      width: 300,
      ellipsis: true,
    },
    {
      title: "可信度",
      dataIndex: "confidence_level",
      key: "confidence_level",
      width: 120,
      render: (value) => <Tag color={value === "高" ? "green" : value === "中" ? "gold" : "default"}>{value}</Tag>,
    },
    {
      title: "产业链位置",
      dataIndex: "chain_position",
      key: "chain_position",
      width: 120,
    },
  ];

  const graphOption = {
    tooltip: {
      formatter: (params) => params.data?.name || "",
    },
    legend: {
      top: 0,
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        data: graphData?.nodes || [],
        links: graphData?.links || [],
        categories: graphData?.categories || [],
        edgeSymbol: ["none", "arrow"],
        edgeLabel: {
          show: true,
          formatter: "{c}",
          fontSize: 10,
        },
        label: {
          show: true,
          position: "right",
        },
        force: {
          repulsion: 180,
          edgeLength: 120,
        },
      },
    ],
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
              <div className="tag-block">
                {(record.profile_tags || []).map((tag) => (
                  <Tag key={tag} color="blue">
                    {tag}
                  </Tag>
                ))}
              </div>
            </Card>
          </Col>
          <Col xs={24} xl={14}>
            <Card size="small" title="证据展示">
              <p className="insight-text">{record.evidence_summary}</p>
              <div className="tag-block">
                {(record.data_sources || []).map((source) => (
                  <Tag key={source} color="gold">
                    {source}
                  </Tag>
                ))}
              </div>
              {(record.source_links || []).length > 0 && (
                <div className="evidence-links">
                  {(record.source_links || []).map((link) => (
                    <a key={link} href={link} target="_blank" rel="noreferrer">
                      {link}
                    </a>
                  ))}
                </div>
              )}
              {(record.raw_evidence || []).length > 0 && (
                <div className="evidence-list">
                  {(record.raw_evidence || []).map((item) => (
                    <div key={item} className="evidence-item">
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </Col>
          <Col xs={24} xl={12}>
            <Card size="small" title="上下游 / 关联企业">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="上游企业">
                  {insight?.upstream_enterprises?.join("、") || "暂无"}
                </Descriptions.Item>
                <Descriptions.Item label="下游企业">
                  {insight?.downstream_enterprises?.join("、") || "暂无"}
                </Descriptions.Item>
                <Descriptions.Item label="关联企业">
                  {insight?.related_enterprises?.join("、") || record.related_enterprises?.join("、") || "暂无"}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
          <Col xs={24} xl={12}>
            <Card size="small" title="LLM 辅助分类与摘要">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="LLM 提供方">
                  {insight?.llm_provider || "local-rule"}
                </Descriptions.Item>
                <Descriptions.Item label="建议类型">
                  {insight?.llm_label_suggestion || record.category}
                </Descriptions.Item>
                <Descriptions.Item label="摘要">
                  {insight?.llm_summary || "待生成"}
                </Descriptions.Item>
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
        <section className="hero-panel">
          <div>
            <Text className="eyebrow">NANHAI DATA MAP</Text>
            <Title>南海区数据产业图谱查询系统</Title>
            <Paragraph className="hero-copy">
              严格围绕比赛要求展示企业名、所在镇街、主要类型、分类依据、主营产品，
              并提供文字查询与语音查询入口，方便作品演示和答辩。
            </Paragraph>
          </div>
          <div className="hero-metrics">
            <Card className="metric-card">
              <Statistic
                title="当前已入库企业"
                value={stats?.total || 0}
                suffix={`/ ${stats?.target || 1000}`}
              />
            </Card>
            <Card className="metric-card">
              <Statistic
                title="覆盖镇街"
                value={Object.values(stats?.town_stats || {}).filter(Boolean).length}
                suffix="/ 7"
              />
            </Card>
          </div>
        </section>

        <Row gutter={[16, 16]} className="stats-grid">
          {categoryOptions
            .filter((item) => item.value !== "全部")
            .map((item) => (
              <Col xs={12} md={8} xl={4} key={item.value}>
                <Card className="stats-card">
                  <Statistic
                    title={item.label}
                    value={stats?.category_stats?.[item.value] || 0}
                  />
                </Card>
              </Col>
            ))}
        </Row>

        <Row gutter={[16, 16]} className="stats-grid platform-panels">
          <Col xs={24} xl={10}>
            <Card className="table-card panel-card" title="🤖 AI智能采集引擎">
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                <div>
                  <Text strong>💬 输入采集指令</Text>
                  <Input
                    size="large"
                    value={platformInstruction}
                    placeholder="例如：采集桂城街道的数据服务企业"
                    onChange={(event) => setPlatformInstruction(event.target.value)}
                    style={{ marginTop: 8 }}
                  />
                </div>

                <Button
                  type="primary"
                  size="large"
                  loading={smartCollecting}
                  disabled={!platformInstruction.trim()}
                  onClick={runSmartCollect}
                  block
                >
                  {smartCollecting ? "正在智能采集中..." : "🚀 一键智能采集"}
                </Button>

                {smartCollectResult && (
                  <Alert
                    type="success"
                    showIcon
                    message="✅ 采集完成"
                    description={
                      <div>
                        <p style={{ marginBottom: 6 }}>
                          📊 指令解析：类型{" "}
                          <Tag color="blue">{smartCollectResult.parsed?.category || "未指定"}</Tag>
                          {" "}镇街{" "}
                          <Tag color="green">{smartCollectResult.parsed?.town || "未指定"}</Tag>
                        </p>
                        <p style={{ marginBottom: 6 }}>
                          🔧 执行流程：{smartCollectResult.tasks_executed?.map((t) => {
                            const names = { search_engine: "🔎多源搜索", amap_poi: "🔍高德POI", company_website: "📝官网快照" };
                            return names[t] || t;
                          }).join(" → ")} → 🤖AI自动分类
                        </p>
                        <p style={{ marginBottom: 6 }}>
                          ✅ 采集: {smartCollectResult.collected_count}条 |{" "}
                          入库: {smartCollectResult.imported_count}条 |{" "}
                          AI分类: {smartCollectResult.classified_count}条
                        </p>
                        <p style={{ marginBottom: 0 }}>
                          📈 数据库现有企业：<strong>{smartCollectResult.total_enterprises}</strong> / 1000
                        </p>
                        {smartCollectResult.new_candidates > 0 && (
                          <p style={{ marginTop: 6, color: "#d35400", fontWeight: 600 }}>
                            📋 {smartCollectResult.review_hint || `有 ${smartCollectResult.new_candidates} 家候选企业需要审核`}
                          </p>
                        )}
                      </div>
                    }
                  />
                )}

                {candidates.length > 0 && (
                  <Card
                    size="small"
                    title={
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>📋 待审核候选企业（{candidates.length}家）</span>
                        <Space size="small">
                          <Button size="small" onClick={toggleAll}>
                            {selectedIds.length === candidates.length ? "取消全选" : "全选"}
                          </Button>
                          <Button
                            size="small"
                            type="primary"
                            disabled={selectedIds.length === 0}
                            onClick={approveCandidates}
                          >
                            批量入库 ({selectedIds.length})
                          </Button>
                          <Button
                            size="small"
                            danger
                            disabled={selectedIds.length === 0}
                            onClick={rejectCandidates}
                          >
                            批量删除
                          </Button>
                        </Space>
                      </div>
                    }
                    style={{ marginTop: 12 }}
                  >
                    <div style={{ maxHeight: 360, overflowY: "auto" }}>
                      {candidates.map((item) => (
                        <div
                          key={item.id}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            padding: "10px 0",
                            borderBottom: "1px solid #f0f0f0",
                            cursor: "pointer",
                          }}
                          onClick={() => toggleCandidate(item.id)}
                        >
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(item.id)}
                            onChange={() => toggleCandidate(item.id)}
                            style={{ marginTop: 4, marginRight: 12 }}
                          />
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 600, marginBottom: 4 }}>
                              {item.name}
                              {item.source_url && (
                                <a
                                  href={item.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{ fontSize: 12, marginLeft: 8, color: "#1890ff" }}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  查看来源 →
                                </a>
                              )}
                            </div>
                            <div style={{ fontSize: 13, color: "#666" }}>
                              <Tag color="blue" style={{ marginRight: 6 }}>{item.town}</Tag>
                              <Tag color="gold" style={{ marginRight: 6 }}>{item.category}</Tag>
                              <span style={{ color: "#999" }}>
                                分类依据：{item.category_reason?.substring(0, 40)}
                                {(item.category_reason?.length || 0) > 40 ? "..." : ""}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    已接入数据源：多源搜索 | 高德POI | 企业官网 | AI自动分类 | 企业画像补全
                  </Text>
                </div>
              </Space>
            </Card>
          </Col>
          <Col xs={24} xl={14}>
            <Card className="table-card panel-card graph-panel-card" title="知识图谱可视化">
              {graphData ? (
                <ReactECharts option={graphOption} style={{ height: "100%", minHeight: 420 }} />
              ) : (
                <Empty description="图谱数据加载中" />
              )}
            </Card>
          </Col>
        </Row>

        <Card className="query-card">
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <div>
              <Title level={4}>文字 / 语音查询</Title>
              <Paragraph>
                可以直接输入"查找桂城街道的数据服务企业"这类自然语言，也可以点击语音按钮进行口述查询。
              </Paragraph>
            </div>

            <Space wrap>
              {exampleQueries.map((query) => (
                <Button
                  key={query}
                  type={queryText === query ? "primary" : "default"}
                  ghost={queryText === query}
                  onClick={() => {
                    setQueryText(query);
                    runNaturalLanguageQuery(query);
                  }}
                >
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
                onChange={(event) => setQueryText(event.target.value)}
                onPressEnter={() => runNaturalLanguageQuery(queryText)}
              />
              <Button
                size="large"
                type="primary"
                onClick={() => runNaturalLanguageQuery(queryText)}
              >
                文字查询
              </Button>
              <Button
                size="large"
                className={isListening ? "listening-btn" : ""}
                onClick={handleVoiceSearch}
              >
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
                    <div>
                      查询原文：{queryMeta?.input || queryText || "无"}
                    </div>
                    <div>
                      识别结果：类型 {querySummary.category || "未识别"}；镇街{" "}
                      {querySummary.town || "未识别"}；关键词{" "}
                      {querySummary.keyword || "无"}
                    </div>
                    <div>命中企业：{queryMeta?.total ?? 0} 家</div>
                  </>
                }
              />
            )}

            {querySummary && (
              <Table
                columns={columns}
                dataSource={queryResults}
                loading={queryLoading}
                rowKey="id"
                pagination={false}
                scroll={{ x: 1300 }}
                locale={{ emptyText: <Empty description="当前查询暂无命中企业" /> }}
                size="middle"
              />
            )}
          </Space>
        </Card>

        <Card className="filter-card">
          <Space wrap size="middle">
            <Select
              value={filterCategory}
              options={categoryOptions}
              onChange={setFilterCategory}
              style={{ width: 180 }}
            />
            <Select
              value={filterTown}
              options={townOptions}
              onChange={setFilterTown}
              style={{ width: 180 }}
            />
            <Input.Search
              value={filterKeyword}
              placeholder="按企业名称关键词筛选"
              allowClear
              onChange={(event) => setFilterKeyword(event.target.value)}
              onSearch={handleFilterSearch}
              style={{ width: 320 }}
            />
            <Button onClick={handleFilterSearch}>按条件筛选</Button>
          </Space>
        </Card>

        <Card className="table-card">
          <Table
            columns={columns}
            dataSource={tableData}
            loading={loading}
            rowKey="id"
            scroll={{ x: 1300 }}
            expandable={{
              expandedRowRender,
              onExpand: (expanded, record) => {
                if (expanded) {
                  fetchEnterpriseInsight(record.id);
                }
              },
            }}
            locale={{ emptyText: <Empty description="暂无符合条件的数据" /> }}
            pagination={{
              current: pagination.current,
              pageSize: pagination.pageSize,
              total: pagination.total,
              showSizeChanger: true,
              pageSizeOptions: ["10", "20", "50"],
              showTotal: (total) => `共 ${total} 条企业记录`,
            }}
            onChange={handleTableChange}
          />
        </Card>
      </div>
    </div>
  );
}

export default App;