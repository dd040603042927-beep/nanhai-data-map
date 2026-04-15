import { useEffect, useState } from "react";
import { Card, Select, Table, Typography, Space, Tag, message } from "antd";

const { Title, Paragraph } = Typography;

const categoryOptions = [
  { label: "全部", value: "全部" },
  { label: "数据资源类", value: "数据资源类" },
  { label: "数据技术类", value: "数据技术类" },
  { label: "数据服务类", value: "数据服务类" },
  { label: "数据安全类", value: "数据安全类" },
  { label: "数据基础设施类", value: "数据基础设施类" },
  { label: "其他数据相关类", value: "其他数据相关类" }
];

function App() {
  const [selectedCategory, setSelectedCategory] = useState("全部");
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchEnterprises = async (category) => {
    try {
      setLoading(true);

      let url = "http://127.0.0.1:8000/enterprises/";
      if (category && category !== "全部") {
        url += `?category=${encodeURIComponent(category)}`;
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error("获取企业数据失败");
      }

      const data = await response.json();

      const formattedData = data.map((item) => ({
        key: item.id,
        name: item.name,
        town: item.town,
        category: item.category,
        products: item.products
      }));

      setTableData(formattedData);
    } catch (error) {
      console.error(error);
      message.error("加载企业数据失败，请检查后端是否启动");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEnterprises(selectedCategory);
  }, [selectedCategory]);

  const columns = [
    {
      title: "企业名称",
      dataIndex: "name",
      key: "name"
    },
    {
      title: "镇街",
      dataIndex: "town",
      key: "town"
    },
    {
      title: "分类",
      dataIndex: "category",
      key: "category",
      render: (value) => <Tag>{value}</Tag>
    },
    {
      title: "主营产品",
      dataIndex: "products",
      key: "products"
    }
  ];

  return (
    <div style={{ padding: 24, background: "#f5f5f5", minHeight: "100vh" }}>
      <Card style={{ maxWidth: 1200, margin: "0 auto" }}>
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <div>
            <Title level={2} style={{ marginBottom: 8 }}>
              南海区数据产业企业图谱
            </Title>
            <Paragraph style={{ marginBottom: 0 }}>
              展示后端真实企业数据，支持按分类筛选。
            </Paragraph>
          </div>

          <div style={{ maxWidth: 260 }}>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>按分类筛选</div>
            <Select
              style={{ width: "100%" }}
              value={selectedCategory}
              onChange={setSelectedCategory}
              options={categoryOptions}
            />
          </div>

          <Table
            columns={columns}
            dataSource={tableData}
            loading={loading}
            pagination={{ pageSize: 5 }}
          />
        </Space>
      </Card>
    </div>
  );
}

export default App;