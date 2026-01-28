<script setup lang="ts">
import { useChatStore } from '../stores/chatStore'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { Connection, DataLine, VideoPlay, InfoFilled } from '@element-plus/icons-vue'

const chatStore = useChatStore()
const { selectedMessage } = storeToRefs(chatStore)

const traceLog = computed(() => selectedMessage.value?.traceLog || [])
const sources = computed(() => selectedMessage.value?.sources || [])

// Determine step status color
const getStepStatus = (_step: any) => {
  // Simple heuristic: if we have details, it's likely success unless indicated otherwise
  // Real implementation might need explicit status in trace log
  return 'success' 
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50 border-l border-gray-200">
    <!-- Header -->
    <div class="h-14 border-b border-gray-200 flex items-center px-4 bg-white shrink-0 justify-between">
      <div class="flex items-center gap-2 text-gray-700">
        <el-icon><Connection /></el-icon>
        <span class="font-medium">执行链路溯源</span>
      </div>
      <div v-if="selectedMessage" class="text-xs text-gray-400">
        ID: {{ selectedMessage.id.slice(-6) }}
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-4 custom-scrollbar">
      <div v-if="!selectedMessage" class="h-full flex flex-col items-center justify-center text-gray-400">
        <el-icon :size="48" class="mb-4"><InfoFilled /></el-icon>
        <p>请点击左侧对话消息</p>
        <p class="text-xs mt-1">查看详细的执行过程和上下文</p>
      </div>

      <div v-else-if="!traceLog.length && selectedMessage.role === 'assistant' && selectedMessage.isLoading" class="h-full flex items-center justify-center">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="!traceLog.length && selectedMessage.role === 'assistant'" class="text-center text-gray-400 mt-10">
        <p>该消息无溯源信息</p>
      </div>

      <div v-else class="space-y-6">
        <!-- Timeline -->
        <el-timeline>
          <el-timeline-item
            v-for="(step, index) in traceLog"
            :key="index"
            :type="getStepStatus(step)"
            :icon="VideoPlay"
            size="large"
          >
            <div class="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
              <!-- Step Header -->
              <div class="px-4 py-3 bg-gray-50 border-b border-gray-100 flex justify-between items-center">
                <span class="font-medium text-gray-800 text-sm">{{ step.step }}</span>
                <el-tag v-if="step.strategy" size="small" effect="plain">{{ step.strategy }}</el-tag>
              </div>
              
              <!-- Step Details -->
              <div class="p-4 text-xs">
                
                <!-- Intent Info -->
                <div v-if="step.step === 'Intent Recognition'" class="space-y-2">
                  <div class="flex gap-2">
                    <span class="text-gray-500 w-20 shrink-0">初始意图:</span>
                    <el-tag size="small">{{ step.details.initial_intent }}</el-tag>
                  </div>
                  <div class="flex gap-2">
                    <span class="text-gray-500 w-20 shrink-0">历史上下文:</span>
                    <span class="text-gray-700 truncate block flex-1" :title="step.details.history_used">
                      {{ step.details.history_used ? '已包含' : '无' }}
                    </span>
                  </div>
                </div>

                <!-- SQL Strategy -->
                <div v-if="step.details.type === 'SQL'" class="space-y-3">
                  
                  <!-- Final Result -->
                  <div v-if="step.details.sql_query && !step.details.sql_attempts">
                    <div class="text-gray-500 mb-1">Generated SQL:</div>
                    <div class="bg-gray-800 text-green-400 p-2 rounded font-mono overflow-x-auto">
                      {{ step.details.sql_query }}
                    </div>
                    <div class="mt-2 text-gray-500 mb-1">Raw Result:</div>
                    <pre class="bg-gray-100 p-2 rounded text-gray-600 overflow-x-auto">{{ step.details.raw_result }}</pre>
                  </div>

                  <!-- Iterative SQL Attempts -->
                  <div v-if="step.details.sql_attempts && step.details.sql_attempts.length" class="space-y-4">
                    <div v-for="(attempt, aIdx) in step.details.sql_attempts" :key="aIdx" class="border-l-2 pl-3" :class="attempt.status === 'SUCCESS' ? 'border-green-400' : 'border-gray-300'">
                      <div class="flex items-center gap-2 mb-2">
                        <span class="font-semibold text-gray-700">尝试 #{{ attempt.attempt }}</span>
                        <el-tag size="small" :type="attempt.status === 'SUCCESS' ? 'success' : 'info'">
                          {{ attempt.hint_column ? `字段: ${attempt.hint_column}` : '默认生成' }}
                        </el-tag>
                        <el-tag v-if="attempt.status === 'SUCCESS'" size="small" type="success" effect="dark">成功</el-tag>
                        <el-tag v-else size="small" type="info">未命中</el-tag>
                      </div>

                      <div class="mb-2">
                        <div class="text-[10px] text-gray-400 uppercase mb-0.5">SQL Query</div>
                        <div class="bg-gray-800 text-green-400 p-2 rounded font-mono text-[10px] overflow-x-auto">
                          {{ attempt.sql || '生成失败' }}
                        </div>
                      </div>

                      <div v-if="attempt.result">
                        <div class="text-[10px] text-gray-400 uppercase mb-0.5">Result</div>
                        <pre class="bg-gray-50 p-2 rounded text-gray-600 text-[10px] overflow-x-auto border border-gray-100">{{ attempt.result }}</pre>
                      </div>
                      
                      <div v-if="attempt.error" class="text-red-500 text-[10px] mt-1">
                        Error: {{ attempt.error }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- RAG Strategy -->
                <div v-if="step.details.type === 'RAG'" class="space-y-3">
                  <div v-if="step.details.rag_trace && step.details.rag_trace.length">
                    <div v-for="(round, rIdx) in step.details.rag_trace" :key="rIdx" class="mb-4 last:mb-0 border-l-2 border-blue-200 pl-3">
                      <div class="font-semibold text-blue-600 mb-1">Round {{ round.round }}</div>
                      
                      <!-- Query -->
                      <div class="mb-2">
                        <span class="text-gray-500">检索词:</span>
                        <span class="ml-2 bg-blue-50 px-1 rounded">{{ round.query }}</span>
                      </div>

                      <!-- Judgment -->
                      <div class="mb-2 bg-yellow-50 p-2 rounded border border-yellow-100">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="text-gray-500">LLM 判断:</span>
                          <el-tag size="small" :type="round.llm_judgment.status === 'SOLVED' ? 'success' : 'warning'">
                            {{ round.llm_judgment.status }}
                          </el-tag>
                        </div>
                        <div v-if="round.llm_judgment.clues" class="text-gray-600 mt-1 italic">
                          "{{ round.llm_judgment.clues }}"
                        </div>
                        <div v-if="round.llm_judgment.next_query" class="mt-1 flex gap-2">
                          <span class="text-gray-500">下轮建议:</span>
                          <span class="font-medium text-gray-700">{{ round.llm_judgment.next_query }}</span>
                        </div>
                      </div>

                      <!-- Docs -->
                      <div v-if="round.retrieved_docs.length">
                        <div class="text-gray-500 mb-1">检索到的文档 ({{ round.retrieved_docs.length }}):</div>
                        <el-collapse accordion class="doc-collapse">
                          <el-collapse-item v-for="(doc, dIdx) in round.retrieved_docs" :key="dIdx" :title="`Doc ${dIdx+1} (ID: ${doc.chunk_id})`">
                            <div class="p-2 bg-gray-50 text-gray-600 rounded whitespace-pre-wrap">{{ doc.content }}</div>
                          </el-collapse-item>
                        </el-collapse>
                      </div>
                      <div v-else class="text-gray-400 italic">未找到新文档</div>
                    </div>
                  </div>
                  <div v-else class="text-gray-400">无 RAG 追踪详情</div>
                </div>

              </div>
            </div>
          </el-timeline-item>
        </el-timeline>

        <!-- Final Sources Summary -->
        <div v-if="sources.length" class="mt-6 border-t border-gray-200 pt-4">
          <h3 class="font-medium text-gray-700 mb-3 flex items-center gap-2">
            <el-icon><DataLine /></el-icon> 最终参考来源
          </h3>
          <div class="grid gap-3">
            <div v-for="(src, idx) in sources" :key="idx" class="bg-white p-3 rounded border border-gray-200 text-xs shadow-sm hover:shadow transition-shadow">
              <div class="font-mono text-blue-500 mb-1 text-[10px]">{{ src.chunk_id }}</div>
              <div class="text-gray-600 line-clamp-3 hover:line-clamp-none">{{ src.content }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
:deep(.doc-collapse .el-collapse-item__header) {
  height: 32px;
  line-height: 32px;
  font-size: 12px;
  color: #6b7280;
}
:deep(.doc-collapse .el-collapse-item__content) {
  padding-bottom: 0;
}
</style>
