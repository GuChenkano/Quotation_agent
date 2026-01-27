
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langchain.memory import ChatMessageHistory

class SimpleMemory:
    """
    基于 langchain 实现的简单对话内存，替代 ConversationBufferWindowMemory
    """
    def __init__(self, k=5):
        self.chat_history = ChatMessageHistory()
        self.k = k

    def save_context(self, inputs: Dict[str, str], outputs: Dict[str, str]):
        self.chat_history.add_user_message(inputs.get("input", ""))
        self.chat_history.add_ai_message(outputs.get("output", ""))
        
        # 截断历史，保留最近 k 轮 (2*k 条消息)
        messages = self.chat_history.messages
        if len(messages) > self.k * 2:
            self.chat_history.messages = messages[-(self.k * 2):]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        # 格式化为字符串
        buffer = ""
        for msg in self.chat_history.messages:
            if isinstance(msg, HumanMessage):
                buffer += f"Human: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                buffer += f"AI: {msg.content}\n"
            # 也可以处理 SystemMessage 等其他类型，如果需要的话
        return {"history": buffer}
