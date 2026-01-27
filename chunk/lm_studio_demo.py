import os
import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# --- 1. 连接设置 (必填) ---
# LM Studio 的服务地址
LM_STUDIO_API_BASE = "http://192.168.30.190:1234/v1"
# API Key (必填)
LM_STUDIO_API_KEY = "lm-studio"
#模型参数
MODEL_NAME = "qwen/qwen3-4b-2507"
# 温度
TEMPERATURE = 0.3
# 最大生成 Token 数
MAX_TOKENS = 32000
# 是否启用流式输出
# 推荐开启，以获得打字机效果
STREAMING = True
# --- 3. 对话历史 (预留区域) ---
# 用于存储上下文信息，格式为 langchain_core.messages 中的 Message 对象列表
# 初始可以为空，也可以包含 SystemMessage 来设定 AI 人设
CHAT_HISTORY = [
    SystemMessage(content="·请用中文回答用户的问题。")
]

def get_llm_client():
    """
    初始化并返回 LangChain 的 ChatOpenAI 客户端实例。
    
    Returns:
        ChatOpenAI: 配置好的语言模型客户端
    """
    llm = ChatOpenAI(
        model=MODEL_NAME,
        openai_api_base=LM_STUDIO_API_BASE,
        openai_api_key=LM_STUDIO_API_KEY,
        temperature=TEMPERATURE,
        streaming=STREAMING,
        max_tokens=None if MAX_TOKENS == -1 else MAX_TOKENS
    )
    return llm

def chat_loop():
    """
    主对话循环函数。
    负责接收用户输入，调用模型，处理流式输出，并更新对话历史。
    """
    print(f"正在连接到 LM Studio: {LM_STUDIO_API_BASE}...")
    try:
        llm = get_llm_client()
        # 发送一个简单请求测试连接
        # 注意：如果服务器未启动，这里会抛出异常
        print("连接成功！开始对话 (输入 'quit' 或 'exit' 退出):")
        print("-" * 50)
    except Exception as e:
        print(f"\n连接失败: {e}")
        print("请检查 LM Studio 是否已启动 Server 功能，并确认 IP 和端口配置正确。")
        return

    while True:
        try:
            # 1. 获取用户输入
            user_input = input("\n你: ").strip()
            
            if user_input.lower() in ["quit", "exit"]:
                print("再见！")
                break
            
            if not user_input:
                continue

            # 2. 更新对话历史
            CHAT_HISTORY.append(HumanMessage(content=user_input))

            # 3. 调用模型并处理流式输出
            print("AI: ", end="", flush=True)
            
            full_response = ""
            
            # 使用 stream 方法获取流式响应
            if STREAMING:
                # 监听 AI 生成结果
                for chunk in llm.stream(CHAT_HISTORY):
                    if chunk.content:
                        print(chunk.content, end="", flush=True)
                        full_response += chunk.content
            else:
                # 非流式直接调用
                response = llm.invoke(CHAT_HISTORY)
                full_response = response.content
                print(full_response)

            # 4. 将 AI 回复存入历史
            CHAT_HISTORY.append(AIMessage(content=full_response))
            print("") # 换行

        except KeyboardInterrupt:
            print("\n\n程序已中断。")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            # 发生错误时，可以选择是否从历史中移除刚才的用户提问
            # CHAT_HISTORY.pop() 

if __name__ == "__main__":
    chat_loop()
