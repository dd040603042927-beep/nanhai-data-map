import { useEffect, useState } from "react";
import {
  Card,
  Select,
  Table,
  Typography,
  Space,
  Tag,
  message,
  Input,
  Row,
  Col,
  Statistic,
  Empty,
} from "antd";

const { Title, Paragraph } = Typography;

const categoryOptions = [
  { label: "全部", value: "全部" },
  { label: "数据资源类", value: "数据资源类" },
  { label: "数据技术类", value: "数据技术类" },
  { label: "数据服务类", value: "数据服务类" },
  { label: "数据安全类", value: "数据安全类" },
  { label: "数据基础设施类", value: "数据基础设施类" },
  { label: "其他数据相关类", value: "其他数据相关类" },
];

const townOptions = [
  { label: "全部", value: "全部" },
  { label: "桂城街道", value: "桂城街道" },
  { label: "狮山镇", value: "狮山镇" },
  { label: "大沥镇", value: "大沥镇" },
  { label: "里水镇", value: "里水镇" },
  { label: "丹灶镇", value: "丹灶镇" },
  { label: "西樵镇", value: "西樵镇" },
  { label: "九江镇", value: "九江镇" },
];

function App() {
  const [selectedCategory, setSelectedCategory] = useState("全部");
  const [selectedTown, setSelectedTown] = useState("全部");
  const [keyword, setKeyword] = useState("");
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);

  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 5,
    total: 0,
  });

  const fetchEnterprises = async ({
    category = selectedCategory,
    town = selectedTown,
    page = pagination.current,
    pageSize = pagination.pageSize,
    keywordValue = keyword,
  } = {}) => {
    try {
      setLoading(true);

      const params = new URLSearchParams();

      if (category && category !== "全部") {
        params.append("category", category);
      }

      if (town && town !== "全部") {
        params.append("town", town);
      }

      if (keywordValue && keywordValue.trim()) {
        params.append("keyword", keywordValue.trim());
      }

      params.append("page", String(page));
      params.append("page_size", String(pageSize));

      const url = `http://127.0.0.1:8000/enterprises/?${params.toString()}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error("获取企业数据失败");
      }

      const data = await response.json();

      const items = Array.isArray(data.items) ? data.items : [];

      const formattedData = items.map((item) => ({
        key: item.id,
        id: item.id,
        name: item.name || "",
        town: item.town || "",
        category: item.category || "",
        products: item.products || "",
      }));

      setTableData(formattedData);

      setPagination((prev) => ({
        ...prev,
        current: data.page || 1,
        pageSize: data.page_size || 5,
        total: data.total || 0,
      }));
    } catch (error) {
      console.error(error);
      message.error("加载企业数据失败，请检查后端是否启动");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEnterprises({
      category: selectedCategory,
      town: selectedTown,
      page: 1,
      pageSize: pagination.pageSize,
      keywordValue: keyword,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCategory, selectedTown]);

  const columns = [
    {
      title: "企业名称",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "镇街",
      dataIndex: "town",
      key: "town",
    },
    {
      title: "分类",
      dataIndex: "category",
      key: "category",
      render: (value) => <Tag>{value}</Tag>,
    },
    {
      title: "主营产品",
      dataIndex: "products",
      key: "products",
    },
  ];

  const totalCount = pagination.total;
  const serviceCount = tableData.filter(
    (item) => item.category === "数据服务类"
  ).length;
  const techCount = tableData.filter(
    (item) => item.category === "数据技术类"
  ).length;

  const handleTableChange = (newPagination) => {
    fetchEnterprises({
      category: selectedCategory,
      town: selectedTown,
      page: newPagination.current,
      pageSize: newPagination.pageSize,
      keywordValue: keyword,
    });
  };

  const handleSearch = () => {
    fetchEnterprises({
      category: selectedCategory,
      town: selectedTown,
      page: 1,
      pageSize: pagination.pageSize,
      keywordValue: keyword,
    });
  };

  return (
    <div style={{ padding: 24, background: "#f5f5f5", minHeight: "100vh" }}>
      <Card style={{ maxWidth: 1200, margin: "0 auto" }}>
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <div>
            <Title level={2} style={{ marginBottom: 8 }}>
              南海区数据产业企业图谱
            </Title>
            <Paragraph style={{ marginBottom: 0 }}>
              展示后端真实企业数据，支持按分类、镇街筛选，支持关键词搜索和分页。
            </Paragraph>
          </div>

          <Row gutter={16}>
            <Col span={8}>
              <Card>
                <Statistic title="企业总数" value={totalCount} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="当前页数据服务类数量" value={serviceCount} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="当前页数据技术类数量" value={techCount} />
              </Card>
            </Col>
          </Row>

          <Space wrap size="middle">
            <div style={{ width: 220 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>按分类筛选</div>
              <Select
                style={{ width: "100%" }}
                value={selectedCategory}
                onChange={(value) => setSelectedCategory(value)}
                options={categoryOptions}
              />
            </div>

            <div style={{ width: 220 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>按镇街筛选</div>
              <Select
                style={{ width: "100%" }}
                value={selectedTown}
                onChange={(value) => setSelectedTown(value)}
                options={townOptions}
              />
            </div>

            <div style={{ width: 260 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>按企业名称搜索</div>
              <Input.Search
                placeholder="输入企业名称关键词"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onSearch={handleSearch}
                allowClear
              />
            </div>
          </Space>

          <Table
            columns={columns}
            dataSource={tableData}
            loading={loading}
            locale={{
              emptyText: <Empty description="暂无符合条件的企业数据" />,
            }}
            pagination={{
              current: pagination.current,
              pageSize: pagination.pageSize,
              total: pagination.total,
              showSizeChanger: true,
              pageSizeOptions: ["5", "10", "20"],
              showTotal: (total) => `共 ${total} 条`,
            }}
            onChange={handleTableChange}
          />
        </Space>
      </Card>
    </div>
  );
}

export default App;