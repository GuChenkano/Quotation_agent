import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { sendMessage, type ChatResponse } from '../api'
import { ElMessage } from 'element-plus'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  traceLog?: any[]
  timestamp: number
  isLoading?: boolean
  sources?: any[]
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const selectedMessageId = ref<string | null>(null)
  const isGlobalLoading = ref(false)
  const sessionId = ref(`session_${Date.now()}`)

  const selectedMessage = computed(() => {
    return messages.value.find(m => m.id === selectedMessageId.value) || null
  })

  const addMessage = (role: 'user' | 'assistant', content: string) => {
    const msg: Message = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      role,
      content,
      timestamp: Date.now()
    }
    messages.value.push(msg)
    return msg
  }

  const sendUserMessage = async (content: string) => {
    if (!content.trim()) return
    
    // Add user message
    addMessage('user', content)
    
    // Add placeholder assistant message
    const loadingMsg = addMessage('assistant', '')
    loadingMsg.isLoading = true
    isGlobalLoading.value = true
    
    // Select the loading message to show trace placeholder if needed (optional)
    selectedMessageId.value = loadingMsg.id

    try {
      const response: ChatResponse = await sendMessage(content, sessionId.value)
      
      // Update assistant message
      loadingMsg.content = response.answer
      loadingMsg.traceLog = response.trace_log
      loadingMsg.sources = response.sources
      loadingMsg.isLoading = false
      
      // Auto-select to show new trace
      selectedMessageId.value = loadingMsg.id
      
    } catch (error: any) {
      console.error('Failed to send message:', error)
      loadingMsg.content = '抱歉，系统处理您的请求时遇到错误。'
      loadingMsg.isLoading = false
      ElMessage.error(error.message || '发送失败')
    } finally {
      isGlobalLoading.value = false
    }
  }

  const selectMessage = (id: string) => {
    selectedMessageId.value = id
  }

  return {
    messages,
    selectedMessageId,
    selectedMessage,
    isGlobalLoading,
    sendUserMessage,
    selectMessage
  }
})
