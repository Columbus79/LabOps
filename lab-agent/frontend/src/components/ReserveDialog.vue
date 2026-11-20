<template>
  <div>
    <el-dialog
      :model-value="visible"
      title="预约"
      width="450"
      @open="formRef.resetFields()"
      @close="emit('update:visible', false)"
    >
      <!-- 冒号:是绑定form表单 -->
      <!-- formRef是在表单校验的时候发挥作用 就是去校验当前这个表单里面的form信息是否合理 强调当前 -->
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="80px"
        style="width: 100%; padding-right: 30px; padding-top: 16px"
      >
        <el-form-item label="实验室">
          <el-input :model-value="labName" disabled />
        </el-form-item>
        <el-form-item label="设备">
          <el-input :model-value="equipmentName" disabled />
        </el-form-item>
        <el-form-item label="预约日期" prop="date">
          <el-date-picker
            v-model="form.date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="请选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-time-picker
            v-model="form.start_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="请选择开始时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_time">
          <el-time-picker
            v-model="form.end_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="请选择结束时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input type="textarea" v-model="form.remark" placeholder="请输入备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="emit('update:visible', false)"> 取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { createReservationApi } from '@/api/reservation'
import { ElMessage } from 'element-plus'
import { ref, reactive } from 'vue'
const props = defineProps({
  visible: Boolean,
  labId: Number,
  labName: String,
  equipmentId: Number,
  equipmentName: String
})
const submitting = ref(false)
const emit = defineEmits(['update:visible'])
const formRef = ref()
const form = reactive({
  date: '',
  start_time: '09:00',
  end_time: '18:00',
  remark: ''
})
const rules = {
  date: [{ required: true, message: '请选择预约日期', trigger: 'blur' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'blur' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'blur' }]
}

const handleSubmit = async (data) => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const res = await createReservationApi({
      lab_id: props.labId,
      equipment_id: props.equipmentId,
      ...form
    })
    if (res.code === 200) {
      ElMessage.success('预约已提交 请等待审核')
      emit('update:visible', false)
    }
  } finally {
    submitting.value = false
  }
}
</script>
