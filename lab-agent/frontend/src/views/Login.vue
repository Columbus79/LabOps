<template>
  <div class="longin-conteainer">
    <div class="longin-box">
      <h1 style="font-size: 28px">LabOps 实验室运营平台</h1>
      <div style="margin-top: 5px; margin-bottom: 30px">实验室资源管理与智能运营</div>

      <el-form ref="formRef" :rules="rules" :model="form" label-width="0px" style="width: 100%">
        <el-form-item prop="username">
          <el-input
            size="large"
            v-model="form.username"
            placeholder="请输入账号"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            type="password"
            size="large"
            v-model="form.password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <div>
          <el-button
            size="large"
            type="primary"
            style="width: 100%"
            @click="Login"
            :loading="loadingValue"
            >登 陆</el-button
          >
          <div style="text-align: right; margin-top: 2cqw">
            还没有账号? 请<router-link style="color: var(--el-color-primary)" to="/register"
              >注册</router-link
            >
          </div>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { loginApi } from '@/api/auth'
import { useUser } from '@/utils/user'

const { saveLoginData } = useUser()
const formRef = ref()

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const router = useRouter()

const form = reactive({
  username: '',
  password: ''
})

const loadingValue = ref(false)

const Login = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loadingValue.value = true
  try {
    const res = await loginApi(form)
    console.log(res)
    if (res.code === 200) {
      saveLoginData(res.data)
      ElMessage.success('登录成功')
      await router.push('/manager/home')
    }
  } finally {
    loadingValue.value = false
  }
}
</script>

<style scoped>
.longin-conteainer {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
}

.longin-box {
  width: 380px;
  border-radius: 8px;
  box-shadow: 0 8px 12px rgba(0, 0, 0, 0.1);
  padding: 30px;
  text-align: center;
}
</style>
