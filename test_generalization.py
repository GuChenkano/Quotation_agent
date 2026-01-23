
import unittest
import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from agent import RAGAgent
from config import JSON_DATA_PATH

class TestGeneralization(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_data")
        self.test_dir.mkdir(exist_ok=True)
        
        # 1. 创建模拟联络名单数据 (扁平结构)
        self.contacts_file = self.test_dir / "contacts.json"
        self.contacts_data = [
            {"emp_id": "101", "name": "张三", "dept": "研发部", "title": "工程师", "email": "zhangsan@example.com"},
            {"emp_id": "102", "name": "李四", "dept": "人力资源", "title": "经理", "email": "lisi@example.com"},
            {"emp_id": "103", "name": "王五", "dept": "研发部", "title": "测试", "email": "wangwu@example.com"}
        ]
        with open(self.contacts_file, 'w', encoding='utf-8') as f:
            json.dump(self.contacts_data, f, ensure_ascii=False)
            
        # 2. 创建模拟订单数据 (完全不同的业务场景)
        self.orders_file = self.test_dir / "orders.json"
        self.orders_data = [
            {"order_id": "ORD001", "product": "笔记本电脑", "amount": 5000, "customer": "A公司", "date": "2023-01-01"},
            {"order_id": "ORD002", "product": "鼠标", "amount": 100, "customer": "B公司", "date": "2023-01-02"},
            {"order_id": "ORD003", "product": "键盘", "amount": 200, "customer": "A公司", "date": "2023-01-03"},
            {"order_id": "ORD004", "product": "显示器", "amount": 1500, "customer": "C公司", "date": "2023-01-04"}
        ]
        with open(self.orders_file, 'w', encoding='utf-8') as f:
            json.dump(self.orders_data, f, ensure_ascii=False)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('agent.RetrievalEngine')
    def test_contacts_scenario(self, MockRetrievalEngine):
        print("\n=== 测试场景 1: 联络名单 ===")
        # Mock retrieval engine to avoid ChromaDB dependency issues during test
        mock_retrieval = MockRetrievalEngine.return_value
        mock_retrieval.phase_logger.get_timings.return_value = {}
        
        # 初始化 Agent，指定场景和数据
        agent = RAGAgent(scenario="企业联络名单", json_path=str(self.contacts_file))
        
        # 测试 1: 统计 (SQL)
        q1 = "研发部有多少人？"
        print(f"Q: {q1}")
        res1 = agent.chat(q1)
        print(f"A: {res1['answer']}")
        self.assertIn("2", str(res1['answer'])) # 应该是2人
        
        # 测试 2: 详情 (SQL)
        q2 = "李四的邮箱是什么？"
        print(f"Q: {q2}")
        res2 = agent.chat(q2)
        print(f"A: {res2['answer']}")
        self.assertIn("lisi@example.com", str(res2['answer']))

    @patch('agent.RetrievalEngine')
    def test_orders_scenario(self, MockRetrievalEngine):
        print("\n=== 测试场景 2: 销售订单 ===")
        # Mock retrieval engine
        mock_retrieval = MockRetrievalEngine.return_value
        mock_retrieval.phase_logger.get_timings.return_value = {}

        # 初始化 Agent，指定场景和数据
        agent = RAGAgent(scenario="销售订单管理", json_path=str(self.orders_file))
        
        # 测试 1: 统计 (SQL)
        q1 = "A公司总共消费了多少钱？"
        print(f"Q: {q1}")
        res1 = agent.chat(q1)
        print(f"A: {res1['answer']}")
        # 5000 + 200 = 5200
        self.assertIn("5200", str(res1['answer']) or str(res1['sources'])) 
        
        # 测试 2: 详情 (SQL)
        q2 = "列出所有金额大于1000的订单产品"
        print(f"Q: {q2}")
        res2 = agent.chat(q2)
        print(f"A: {res2['answer']}")
        self.assertIn("笔记本电脑", str(res2['answer']))
        self.assertIn("显示器", str(res2['answer']))
        self.assertNotIn("鼠标", str(res2['answer']))

if __name__ == "__main__":
    unittest.main()
