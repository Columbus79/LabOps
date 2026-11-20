<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px">
        <div>
          <div style="font-size: 22px; font-weight: 700; color: #303133">
            你好，{{ userInfo?.name || '同学' }}
          </div>
          <div style="margin-top: 8px; color: #909399; font-size: 14px">
            欢迎使用 LabOps 实验室运营平台 · 当前身份：{{ roleLabel }}
          </div>
        </div>
        <el-button type="primary" @click="$router.push('/manager/ai-chat')">打开 AI 助手</el-button>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :lg="8" v-for="item in cards" :key="item.label">
        <el-card shadow="hover" style="margin-bottom: 16px">
          <div style="color: #909399; font-size: 13px">{{ item.label }}</div>
          <div style="margin-top: 8px; font-size: 28px; font-weight: 700">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-alert v-if="error" :title="error" type="warning" :closable="false" show-icon />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useUser } from '@/utils/user'
import { getDashboardSummary } from '@/api/operations'

const { userInfo } = useUser()
const stats = ref(null)
const error = ref('')
const roleLabel = computed(() => (userInfo.value?.role === 'admin' ? '管理员' : '学生'))
const cards = computed(() => {
  if (!stats.value) return []
  return [
    { label: '实验室 / 开放', value: `${stats.value.labs_total} / ${stats.value.labs_open}` },
    { label: '正常设备 / 维修中', value: `${stats.value.equipment_normal} / ${stats.value.equipment_maintenance}` },
    { label: '待审核预约', value: stats.value.reservations_pending },
    { label: '已通过预约', value: stats.value.reservations_approved }
  ]
})

onMounted(async () => {
  try {
    const response = await getDashboardSummary()
    stats.value = response.data
  } catch {
    error.value = '当前无法加载实时统计，请稍后重试。'
  }
})
</script>
