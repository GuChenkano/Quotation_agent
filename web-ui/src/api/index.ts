import axios from 'axios'

const api = axios.create({
  baseURL: '/api', // Vite proxy handles the redirect to http://127.0.0.1:8000
  timeout: 60000, // 60s timeout for long RAG chains
})

export interface ChatResponse {
  answer: string
  sources: any[]
  timing: Record<string, number>
  sql_query?: string
  evaluation?: any
  raw_result?: any
  trace_log: any[]
}

export const sendMessage = async (question: string, sessionId: string = 'default_web'): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>('/chat', {
    question,
    session_id: sessionId
  })
  return response.data
}

export const checkHealth = async () => {
  const response = await api.get('/health')
  return response.data
}
