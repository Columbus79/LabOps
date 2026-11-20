<template>
  <div>
    <el-alert
      v-if="isAdmin && untracked.length"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #title>{{ untracked.length }} 台设备处于维修状态，但没有进行中的工单</template>
      <template #default>
        请先核实设备情况；确认故障后可在下方登记工单，不推断旧记录中的故障原因。
        <span v-for="item in untracked" :key="item.id" style="margin-left: 8px">
          {{ item.lab_name }} / {{ item.name }}（#{{ item.id }}）
        </span>
      </template>
    </el-alert>

    <el-card style="margin-bottom: 16px">
      <template #header>
        <div>{{ isAdmin ? '登记设备故障' : '申报设备故障' }}</div>
        <div style="font-size: 13px; color: #666; margin-top: 4px">
          {{ isAdmin
            ? '管理员也可登记故障；工单创建后由管理员推进维修。'
            : '请选择设备并说明实际故障。提交后，你只能查看自己申报的工单。' }}
        </div>
      </template>
      <el-form :model="form" label-width="90px">
        <el-form-item label="设备" required>
          <el-select
            v-model="form.equipment_id"
            filterable
            remote
            reserve-keyword
            clearable
            :remote-method="searchEquipment"
            :loading="equipmentLoading"
            placeholder="搜索设备名称"
            style="width: 100%"
            @visible-change="(visible) => visible && searchEquipment('')"
          >
            <el-option
              v-for="item in equipmentOptions"
              :key="item.id"
              :label="equipmentLabel(item)"
              :value="item.id"
              :disabled="item.status === 2"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="故障说明" required>
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="请描述实际观察到的故障，勿猜测原因"
          />
        </el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">提交故障申报</el-button>
      </el-form>
    </el-card>

    <el-card>
      <template #header>{{ isAdmin ? '全部维修工单 · 管理员处理' : '我提交的故障申报' }}</template>
      <el-table
        :data="tickets"
        v-loading="loading"
        :empty-text="isAdmin ? '暂无维修工单' : '你还没有提交故障申报'"
      >
        <el-table-column prop="id" label="工单" width="80" />
        <el-table-column label="设备" min-width="180">
          <template #default="{ row }">
            {{ row.lab_name || '未知实验室' }} / {{ row.equipment_name || `设备 #${row.equipment_id}` }}
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" prop="reporter_name" label="申报人" width="110" />
        <el-table-column prop="description" label="故障说明" min-width="200" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">{{ statusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column prop="repair_notes" label="维修说明" min-width="160" />
        <el-table-column v-if="isAdmin" label="处理" min-width="230">
          <template #default="{ row }">
            <template v-if="row.status !== 'completed'">
              <el-input v-model="notes[row.id]" placeholder="维修说明" size="small" style="width: 120px" />
              <el-button
                v-if="row.status === 'reported'"
                link
                type="primary"
                :loading="updatingId === row.id"
                @click="update(row, 'repairing')"
              >开始维修</el-button>
              <el-button
                v-if="row.status === 'repairing'"
                link
                type="success"
                :loading="updatingId === row.id"
                @click="update(row, 'completed')"
              >完成维修</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="justify-content: flex-end; margin-top: 12px"
        @current-change="load"
      />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUser } from '@/utils/user'
import { getEquipmentPageList } from '@/api/equipment'
import {
  getMaintenanceTickets,
  getUntrackedMaintenanceEquipment,
  reportMaintenance,
  updateMaintenance
} from '@/api/operations'

const { userInfo } = useUser()
const isAdmin = computed(() => userInfo.value?.role === 'admin')
const tickets = ref([])
const untracked = ref([])
const equipmentOptions = ref([])
const loading = ref(false)
const equipmentLoading = ref(false)
const submitting = ref(false)
const updatingId = ref(null)
const notes = reactive({})
const form = reactive({ equipment_id: null, description: '' })
const page = ref(1)
const pageSize = 20
const total = ref(0)

const statusLabel = (status) => ({ reported: '待处理', repairing: '维修中', completed: '已完成' })[status] || status
const equipmentLabel = (item) => {
  const state = item.status === 2 ? '已停用' : item.status === 0 ? '维修状态' : '正常'
  return `${item.lab_name} / ${item.name}（#${item.id}，${state}）`
}

const searchEquipment = async (keywords) => {
  equipmentLoading.value = true
  try {
    const response = await getEquipmentPageList({ page: 1, page_size: 100, keywords: keywords || undefined })
    equipmentOptions.value = response.data?.list || []
  } finally {
    equipmentLoading.value = false
  }
}

const load = async () => {
  loading.value = true
  try {
    const response = await getMaintenanceTickets({ page: page.value, page_size: pageSize })
    tickets.value = response.data?.list || []
    total.value = response.data?.total || 0
    if (isAdmin.value) {
      const pending = await getUntrackedMaintenanceEquipment()
      untracked.value = pending.data || []
    }
  } finally {
    loading.value = false
  }
}

const submit = async () => {
  if (!form.equipment_id) return ElMessage.warning('请先选择设备')
  if (form.description.trim().length < 5) return ElMessage.warning('请至少填写 5 个字符的故障说明')
  submitting.value = true
  try {
    await reportMaintenance({ equipment_id: form.equipment_id, description: form.description.trim() })
    form.equipment_id = null
    form.description = ''
    page.value = 1
    await load()
    await searchEquipment('')
    ElMessage.success('故障申报已提交')
  } finally {
    submitting.value = false
  }
}

const update = async (ticket, status) => {
  updatingId.value = ticket.id
  try {
    await updateMaintenance(ticket.id, { status, repair_notes: notes[ticket.id] || null })
    delete notes[ticket.id]
    await load()
    await searchEquipment('')
    ElMessage.success(status === 'completed' ? '维修已完成，设备状态已恢复' : '工单已进入维修中')
  } finally {
    updatingId.value = null
  }
}

onMounted(() => {
  load()
  searchEquipment('')
})
</script>
