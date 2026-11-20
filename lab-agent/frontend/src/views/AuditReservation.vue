<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          <span>预约审核与异常处理</span>
        </div>
      </template>
      <div style="margin-bottom: 10px">
        <el-select
          placeholder="请选择状态"
          v-model="params.status"
          style="width: 200px; margin-right: 8px"
          clearable
          @change="handleSearch"
          @clear="handleSearch"
        >
          <el-option :value="0" label="待审核" />
          <el-option :value="1" label="已通过" />
          <el-option :value="2" label="已拒绝" />
          <el-option :value="3" label="已取消" />
          <el-option :value="4" label="使用中" />
          <el-option :value="5" label="已完成" />
          <el-option :value="6" label="未签到" />
          <el-option :value="7" label="故障中断" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
      </div>
      <el-table
        :header-cell-style="{ background: '#f5f5f5', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="lab_name" label="实验室" />
        <el-table-column prop="type" label="预约类型">
          <template #default="{ row }">
            <el-tag :type="row.type === '实验室' ? 'success' : 'primary'">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设备">
          <template #default="{ row }">
            {{ row.equipment_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="date" label="日期" />
        <el-table-column label="预约时段">
          <template #default="{ row }"> {{ row.start_time }} - {{ row.end_time }} </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" />
        <el-table-column prop="exception_reason" label="异常原因" min-width="130" />
        <el-table-column prop="user_name" label="预约入" width="100" />
        <el-table-column label="预约状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240">
          <template #default="{ row }">
            <template v-if="row.status === 0">
              <el-button type="success" text bg @click="handleAudit(row, 1)">通过</el-button>
              <el-button type="danger" text bg @click="handleAudit(row, 2)">拒绝</el-button>
            </template>
            <el-button v-if="row.status === 4" type="success" text bg @click="resolve(row, 'complete')">结束使用</el-button>
            <el-button v-if="[0, 1, 4].includes(row.status)" type="danger" text bg @click="resolve(row, 'interrupt')">异常中断</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.page_size"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { auditReservationApi, getReservationPageList, resolveReservationApi } from '@/api/reservation'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ref, reactive, onMounted } from 'vue'

const tableData = ref([])
const loading = ref(false)
const total = ref(0)

const statusType = (status) => {
  return { 0: 'warning', 1: 'success', 2: 'danger', 3: 'info', 4: 'primary', 5: 'success', 6: 'warning', 7: 'danger' }[status] || '-'
}
const statusText = (status) => {
  return { 0: '待审核', 1: '已通过', 2: '已拒绝', 3: '已取消', 4: '使用中', 5: '已完成', 6: '未签到', 7: '故障中断' }[status]
}

const params = reactive({
  page: 1,
  page_size: 10,
  status: 0
})

const load = async () => {
  loading.value = true
  try {
    const res = await getReservationPageList(params)
    if (res.code === 200) {
      tableData.value = res.data?.list
      total.value = res.data?.total
    }
  } finally {
    loading.value = false
  }
}

const handleAudit = (row, status) => {
  const action = status == 1 ? '通过' : '拒绝'
  ElMessageBox.confirm(`${action} [${row.lab_name}]的预约?`, '审核', { type: 'warning' }).then(
    async () => {
      const res = await auditReservationApi(row.id, status)
      if (res.code === 200) {
        ElMessage.success(`审核${action}`)
        load()
      }
    }
  )
}

const resolve = async (row, action) => {
  let answer
  try {
    answer = await ElMessageBox.prompt('请填写异常处理原因（至少 3 字）', '预约异常处理', {
      inputPattern: /^.{3,255}$/,
      inputErrorMessage: '请填写 3 至 255 字的原因'
    })
  } catch { return }
  await resolveReservationApi(row.id, { action, reason: answer.value })
  ElMessage.success('预约状态已更新')
  await load()
}

const handleSearch = () => {
  params.page = 1
  load()
}

onMounted(() => {
  load()
})
</script>
