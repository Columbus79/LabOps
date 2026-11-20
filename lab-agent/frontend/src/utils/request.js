import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router/index'
import { getToken, logout } from './auth'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000
})

service.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

service.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data?.code !== 200) {
      ElMessage.error(data?.message || '请求失败')
      if (data?.code === 401) {
        logout()
        router.replace('/login')
      }
      return Promise.reject(data)
    }
    return data
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.message || error.response?.data?.detail
    if (status === 401) {
      ElMessage.error('登录已失效，请重新登录')
      logout()
      router.replace('/login')
    } else if (error.response) {
      ElMessage.error(message || `请求失败 (${status})`)
    } else if (error.code !== 'ERR_CANCELED') {
      ElMessage.error('网络异常，请检查后端服务')
    }
    return Promise.reject(error)
  }
)

export default service
