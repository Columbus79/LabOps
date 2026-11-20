<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          <span>实验室管理</span>
        </div>
      </template>
      <div style="margin-bottom: 10px">
        <el-input
          placeholder="请输入名称查询"
          v-model="params.keyWords"
          style="width: 200px; margin-right: 8px"
          @keyup.enter="handleSearch"
          clearable
          @clear="handleSearch"
          #
          清空时触发handleSearch
        ></el-input>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button type="success" :icon="Plus" @click="handleCreate">新增</el-button>
      </div>
      <el-table
        :header-cell-style="{ background: '#f5f5f5', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="简介" />
        <el-table-column prop="img" label="封面">
          <template #default="{ row }">
            <div style="min-height: 50px">
              <img
                v-if="row.img"
                style="display: black; width: 50px; height: 50px"
                :src="row.img"
                alt=""
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" />
        <el-table-column prop="capacity" label="容量" />
        <el-table-column label="开放时间">
          <template #default="{ row }">
            {{ row.open_time && row.close_time
              ? `${row.open_time} - ${row.close_time}` : '未配置（不可预约）' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '开启' : '关闭' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button type="primary" text bg @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 1" type="danger" text bg @click="handleDelete(row)">关闭</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.pageSize"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑实验室' : '新增实验室'" width="450">
      <!-- 冒号:是绑定form表单 -->
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="80px"
        style="width: 100%; padding-right: 30px; padding-top: 16px"
        v-loading="loading"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>

        <el-form-item label="简介">
          <el-input type="textarea" v-model="form.description" placeholder="请输入实验室简介" />
        </el-form-item>
        <el-form-item label="封面">
          <el-upload
            class="avatar-uploader"
            :http-request="handleFileUpload"
            :show-file-list="false"
            accept="image/jpeg,image/png,image/gif,image/webp"
            :before-upload="beforeAvatarUpload"
          >
            <img v-if="form.img" :src="form.img" class="avatar" />
            <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
          </el-upload>
        </el-form-item>
        <el-form-item label="位置" prop="location">
          <el-input type="textarea" v-model="form.location" placeholder="请输入实验室位置" />
        </el-form-item>
        <el-form-item label="容量" prop="capacity">
          <el-input-number
            :min="1"
            type="textarea"
            v-model="form.capacity"
            placeholder="请输入实验室容量"
          />
        </el-form-item>
        <el-form-item label="开放时段">
          <el-time-picker
            v-model="form.openTime"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="开始时间"
            style="width: 140px; margin-right: 8px"
          />
          <el-time-picker
            v-model="form.closeTime"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="结束时间"
            style="width: 140px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"> 取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { createLabApi, deleteLabApi, getLabPageList, updateLabApi } from '@/api/lab'
import { Search, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ref, reactive, onMounted } from 'vue'
import { uploadFileApi } from '@/api/file'

const loading = ref(false)
const tableData = ref([])
const total = ref(0) //总条数
const dialogVisible = ref(false)
const formLoading = ref(false)
const formRef = ref()
const params = reactive({
  page: 1,
  pageSize: 10,
  keyWords: ''
})

const form = reactive({
  name: '',
  description: '',
  img: '',
  location: '',
  capacity: 1,
  openTime: '',
  closeTime: '',
  status: 1
})

const rules = {
  name: [{ required: true, message: '请输入实验室名称', trigger: 'blur' }],
  capacity: [{ required: true, message: '请输入实验室容量', trigger: 'blur' }]
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    name: '',
    description: '',
    img: '',
    location: '',
    capacity: 20,
    openTime: '08:00',
    closeTime: '18:00',
    status: 1
  })
}

const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    name: row.name,
    description: row.description,
    img: row.img,
    location: row.location,
    capacity: row.capacity,
    openTime: row.open_time,
    closeTime: row.close_time,
    status: row.status
  })
  dialogVisible.value = true
}

// 关闭实验室并保留历史
const handleDelete = async (row) => {
  ElMessageBox.confirm(`确认关闭实验室 [${row.name}]？历史记录会保留。`, '确认关闭', { type: 'warning' }).then(
    async () => {
      const res = await deleteLabApi(row.id)
      if (res.code === 200) {
        ElMessage.success('实验室已关闭')
        load()
      }
    }
  )
}

// 保存
const handleSave = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const payload = {
    name: form.name,
    description: form.description,
    img: form.img,
    location: form.location,
    capacity: form.capacity,
    open_time: form.openTime,
    close_time: form.closeTime,
    status: form.status
  } // 统一转换后端响应格式

  formLoading.value = true
  try {
    const res = form.id ? await updateLabApi(form.id, payload) : await createLabApi(payload)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success(res.message)
      load()
    }
  } finally {
    formLoading.value = false
  }
}
// 加载分页数据
const load = async () => {
  loading.value = true
  try {
    const res = await getLabPageList({
      page: params.page,
      page_size: params.pageSize,
      keywords: params.keyWords
    })
    if (res.code === 200) {
      tableData.value = res.data?.list
      total.value = res.data?.total
    }
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  params.page = 1
  load()
}

const handleFileUpload = async ({ file }) => {
  try {
    const res = await uploadFileApi(file)
    if (res.code === 200) {
      form.img = res.data?.url
    }
  } catch {}
}
// 前端处理传入后端的头像规格的逻辑
const beforeAvatarUpload = (file) => {
  const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  // 类型不符合
  if (!imageTypes.includes(file.type)) {
    ElMessage.error('只能上传图片')
    return false
  }
  // 文件大小大于2M处理逻辑
  if (file.size / 1024 / 1024 > 10) {
    ElMessage.error('上传图拍呢大小不能超过10M')
    return false
  }
  return true
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.avatar-uploader .avatar {
  width: 130px;
  height: 130px;
  display: block;
}
</style>
<style>
.avatar-uploader .el-upload {
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
}
.avatar-uploader .el-upload:hover {
  border-color: var(--el-color-primary);
}
.el-icon.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 130px;
  height: 130px;
  text-align: center;
}
</style>
