<script setup lang="ts">
import ChatPanel from './components/ChatPanel.vue'
import TracePanel from './components/TracePanel.vue'
</script>

<template>
  <div class="h-screen w-full flex flex-col md:flex-row overflow-hidden bg-gray-50">
    <!-- Left: Chat Area (60%) -->
    <div class="w-full md:w-[60%] h-full flex flex-col border-r border-gray-200 bg-white shadow-sm z-10">
      <ChatPanel />
    </div>

    <!-- Right: Trace/Workflow Area (40%) -->
    <div class="w-full md:w-[40%] h-full bg-gray-50 flex flex-col overflow-hidden">
      <TracePanel />
    </div>
  </div>
</template>

<style>
/* Global scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
