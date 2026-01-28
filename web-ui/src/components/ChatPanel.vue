<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chatStore'
import { User, Monitor, Loading, ChatLineRound } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'

const chatStore = useChatStore()
const { messages, selectedMessageId, isGlobalLoading } = storeToRefs(chatStore)
const inputValue = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

watch(() => messages.value.length, scrollToBottom)
watch(() => messages.value[messages.value.length - 1]?.content, scrollToBottom, { deep: true })

const handleSend = async () => {
  if (!inputValue.value.trim() || isGlobalLoading.value) return
  const content = inputValue.value
  inputValue.value = ''
  await chatStore.sendUserMessage(content)
}

const handleSelectMessage = (id: string) => {
  chatStore.selectMessage(id)
}

onMounted(() => {
  // Add welcome message if empty
  if (messages.value.length === 0) {
    // Manually add to store without API call
    chatStore.messages.push({
      id: 'welcome',
      role: 'assistant',
      content: '您好！我是智能业务助手。我可以帮您查询企业联络名单、合同信息，或者回答相关业务问题。',
      timestamp: Date.now()
    })
  }
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="h-14 border-b border-gray-100 flex items-center px-6 bg-white shrink-0">
      <el-icon class="mr-2 text-blue-500" :size="20"><ChatLineRound /></el-icon>
      <h1 class="font-semibold text-gray-700">智能对话助手</h1>
      <el-tag v-if="isGlobalLoading" size="small" class="ml-auto" type="warning" effect="light">
        <el-icon class="is-loading mr-1"><Loading /></el-icon>处理中
      </el-tag>
    </div>

    <!-- Messages List -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth">
      <div 
        v-for="msg in messages" 
        :key="msg.id"
        class="flex gap-3 max-w-3xl mx-auto cursor-pointer transition-colors p-2 rounded-lg"
        :class="{ 'bg-blue-50/50': selectedMessageId === msg.id, 'hover:bg-gray-50': selectedMessageId !== msg.id }"
        @click="handleSelectMessage(msg.id)"
      >
        <!-- Avatar -->
        <div 
          class="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
          :class="msg.role === 'user' ? 'bg-indigo-100 text-indigo-600' : 'bg-green-100 text-green-600'"
        >
          <el-icon :size="20">
            <User v-if="msg.role === 'user'" />
            <Monitor v-else />
          </el-icon>
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-medium text-sm text-gray-900">
              {{ msg.role === 'user' ? '用户' : '系统助手' }}
            </span>
            <span class="text-xs text-gray-400">
              {{ new Date(msg.timestamp).toLocaleTimeString() }}
            </span>
            <el-tag v-if="msg.traceLog" size="small" type="info" class="scale-75 origin-left">
              已溯源
            </el-tag>
          </div>
          
          <div 
            class="text-gray-700 leading-relaxed whitespace-pre-wrap break-words text-sm"
            :class="{ 'animate-pulse': msg.isLoading }"
          >
            {{ msg.content || (msg.isLoading ? '正在思考...' : '') }}
          </div>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="p-4 bg-white border-t border-gray-100 shrink-0">
      <div class="max-w-3xl mx-auto relative">
        <el-input
          v-model="inputValue"
          type="textarea"
          :rows="3"
          placeholder="请输入您的问题... (Enter 发送, Shift+Enter 换行)"
          resize="none"
          class="custom-input"
          @keydown.enter.exact.prevent="handleSend"
        />
        <div class="absolute bottom-2 right-2">
          <el-button 
            type="primary" 
            :loading="isGlobalLoading"
            :disabled="!inputValue.trim()"
            @click="handleSend"
            circle
          >
            <template #icon>
              <el-icon><position-icon /></el-icon> <!-- Using CSS/Text arrow if icon fails or generic Send -->
              <span class="ml-1" v-if="!isGlobalLoading">发送</span>
            </template>
          </el-button>
        </div>
      </div>
      <div class="text-center mt-2 text-xs text-gray-400">
        内容由 AI 生成，请仔细甄别。点击消息可查看执行链路溯源。
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Customizing Element Plus Input */
:deep(.el-textarea__inner) {
  padding-right: 80px; /* Space for button */
  border-radius: 12px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}
:deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px #3b82f6 inset;
}
</style>
