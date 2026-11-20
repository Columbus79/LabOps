<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>站内通知</span>
        <el-button link type="primary" @click="markAll">全部标记已读</el-button>
      </div>
    </template>
    <el-empty v-if="items.length === 0" description="暂无通知" />
    <el-timeline v-else>
      <el-timeline-item v-for="item in items" :key="item.id" :timestamp="formatDate(item.create_time)" :type="item.is_read ? 'info' : 'primary'">
        <div style="display: flex; justify-content: space-between; gap: 12px">
          <div>
            <strong>{{ item.title }}</strong>
            <div style="margin-top: 5px; color: #606266">{{ item.message }}</div>
          </div>
          <el-button v-if="!item.is_read" link type="primary" @click="markRead(item)">标记已读</el-button>
        </div>
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getNotifications, markAllNotificationsRead, markNotificationRead } from '@/api/operations'

const items = ref([])
const load = async () => {
  const response = await getNotifications({ page: 1, page_size: 100 })
  items.value = response.data?.list || []
}
const markRead = async (item) => {
  await markNotificationRead(item.id)
  item.is_read = true
  window.dispatchEvent(new Event('notifications-updated'))
}
const markAll = async () => {
  await markAllNotificationsRead()
  items.value.forEach((item) => (item.is_read = true))
  window.dispatchEvent(new Event('notifications-updated'))
  ElMessage.success('通知已全部标记为已读')
}
const formatDate = (value) => (value ? new Date(value).toLocaleString() : '')
onMounted(load)
</script>
