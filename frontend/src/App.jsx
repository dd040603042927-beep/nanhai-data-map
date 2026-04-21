import {
  Alert,
  Button,
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
  const [selectedCategory, setSelectedCategory] = useState("全部");
  const [selectedTown, setSelectedTown] = useState("全部");
  const [keyword, setKeyword] = useState("");
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [querySummary, setQuerySummary] = useState(null);
  const [isListening, setIsListening] = useState(false);
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
      if (!response.ok) {
        throw new Error("获取统计信息失败");
      }

      const data = await response.json();
      setStats(data);
    } catch (error) {
      message.error(error.message || "统计信息加载失败");
    }
  };

  const fetchEnterprises = async ({
    category = selectedCategory,
    town = selectedTown,
    page = 1,
    pageSize = pagination.pageSize,
    keywordValue = keyword,
  } = {}) => {
    try {
      setLoading(true);
      setQuerySummary(null);

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
      setLoading(true);

      const params = new URLSearchParams({
        text: cleanText,
        page: "1",
        page_size: String(pagination.pageSize),
      });

      const response = await fetch(`/api/enterprises/query?${params.toString()}`);
      if (!response.ok) {
        throw new Error("自然语言查询失败");
      }

      const data = await response.json();
      setQuerySummary(data.parsed);
      setSelectedCategory(data.parsed.category || "全部");
      setSelectedTown(data.parsed.town || "全部");
      setKeyword(data.parsed.keyword || "");
      setTableData(formatItems(data.items));
      setPagination({
        current: data.page || 1,
        pageSize: data.page_size || pagination.pageSize,
        total: data.total || 0,
      });
    } catch (error) {
      message.error(error.message || "查询失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchEnterprises();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTableChange = (newPagination) => {
    fetchEnterprises({
      category: selectedCategory,
      town: selectedTown,
      page: newPagination.current,
      pageSize: newPagination.pageSize,
      keywordValue: keyword,
    });
  };

  const handleFilterSearch = () => {
    fetchEnterprises({
      category: selectedCategory,
      town: selectedTown,
      page: 1,
      pageSize: pagination.pageSize,
      keywordValue: keyword,
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
        setKeyword(transcript);
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
  ];

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

        <Card className="query-card">
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <div>
              <Title level={4}>文字 / 语音查询</Title>
              <Paragraph>
                可以直接输入“查找桂城街道的数据服务企业”这类自然语言，也可以点击语音按钮进行口述查询。
              </Paragraph>
            </div>

            <Space wrap>
              {exampleQueries.map((query) => (
                <Button key={query} onClick={() => runNaturalLanguageQuery(query)}>
                  {query}
                </Button>
              ))}
            </Space>

            <div className="query-toolbar">
              <Input
                size="large"
                value={keyword}
                placeholder="例如：帮我找桂城街道的数据技术企业"
                onChange={(event) => setKeyword(event.target.value)}
                onPressEnter={() => runNaturalLanguageQuery(keyword)}
              />
              <Button
                size="large"
                type="primary"
                onClick={() => runNaturalLanguageQuery(keyword)}
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
                description={`类型：${querySummary.category || "未识别"}；镇街：${querySummary.town || "未识别"}；关键词：${querySummary.keyword || "无"}`}
              />
            )}
          </Space>
        </Card>

        <Card className="filter-card">
          <Space wrap size="middle">
            <Select
              value={selectedCategory}
              options={categoryOptions}
              onChange={setSelectedCategory}
              style={{ width: 180 }}
            />
            <Select
              value={selectedTown}
              options={townOptions}
              onChange={setSelectedTown}
              style={{ width: 180 }}
            />
            <Input.Search
              value={keyword}
              placeholder="按企业名称关键词筛选"
              allowClear
              onChange={(event) => setKeyword(event.target.value)}
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
