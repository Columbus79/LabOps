<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap">
        <strong>运营分析</strong>
        <div style="display: flex; gap: 8px">
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
            start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" />
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </div>
      </div>
    </template>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="report">
      <el-row :gutter="12">
        <el-col v-for="item in indicators" :key="item.label" :xs="12" :md="6">
          <el-card shadow="never" style="margin-bottom: 12px">
            <div style="color: #667085; font-size: 13px">{{ item.label }}</div>
            <div style="font-size: 25px; font-weight: 650; margin-top: 6px">{{ item.value }}</div>
          </el-card>
        </el-col>
      </el-row>
      <p style="font-size: 12px; color: #667085">{{ report.definition }}</p>
      <h3>预约趋势</h3>
      <div v-for="item in report.reservation_trend" :key="item.date" style="display: flex; gap: 12px; align-items: center; margin: 5px 0">
        <span style="width: 92px; font-size: 12px">{{ item.date }}</span>
        <div :style="{ height: '12px', width: `${Math.max(3, item.count / maxTrend * 280)}px`, background: '#409eff', borderRadius: '3px' }"></div>
        <span>{{ item.count }}</span>
      </div>
      <h3>实验室利用率</h3>
      <el-table :data="report.labs" empty-text="暂无实验室数据">
        <el-table-column prop="name" label="实验室" />
        <el-table-column prop="used_hours" label="实际使用小时" />
        <el-table-column prop="available_hours" label="可用小时" />
        <el-table-column label="利用率"><template #default="{ row }">{{ percent(row.utilization_rate) }}</template></el-table-column>
      </el-table>
      <h3>设备利用率与维修频率</h3>
      <el-table :data="report.equipments" empty-text="暂无设备数据">
        <el-table-column prop="name" label="设备" />
        <el-table-column prop="used_hours" label="实际使用小时" />
        <el-table-column label="利用率"><template #default="{ row }">{{ percent(row.utilization_rate) }}</template></el-table-column>
        <el-table-column label="维修次数"><template #default="{ row }">{{ repairs(row.id) }}</template></el-table-column>
      </el-table>
    </template>
  </el-card>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getOperationsReport } from '@/api/operations'

const range = ref(null)
const report = ref(null)
const loading = ref(false)
const error = ref('')
const maxTrend = computed(() => Math.max(1, ...(report.value?.reservation_trend || []).map(item => item.count)))
const indicators = computed(() => report.value ? [
  { label: '预约总数', value: report.value.reservation_total },
  { label: '预约通过率', value: percent(report.value.approval_rate) },
  { label: '维修工单', value: report.value.repair_count },
  { label: '平均维修时长', value: report.value.average_repair_hours == null ? '暂无' : `${report.value.average_repair_hours} 小时` },
  { label: '未签到异常', value: report.value.no_show_total }
] : [])
const percent = (value) => value == null ? '暂无' : `${value}%`
const repairs = (id) => report.value?.repair_frequency.find(item => item.equipment_id === id)?.count || 0
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const params = range.value ? { start: range.value[0], end: range.value[1] } : {}
    const response = await getOperationsReport(params)
    report.value = response.data
  } catch { error.value = '运营统计加载失败，请检查日期范围或稍后重试。' }
  finally { loading.value = false }
}
onMounted(load)
</script>
