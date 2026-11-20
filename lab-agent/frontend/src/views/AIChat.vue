<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; align-items: center; gap: 10px">
          <span style="font-size: 16px; font-weight: bold">AI智能助手</span>
          <el-select v-model="conversationId" placeholder="新对话" clearable style="width: 220px" @change="selectConversation">
            <el-option v-for="item in conversations" :key="item.id" :label="item.title" :value="item.id" />
          </el-select>
          <el-button size="small" @click="startNewConversation">新建对话</el-button>
        </div>
      </template>
      <div
        ref="listRef"
        style="
          height: 480px;
          overflow-y: auto;
          padding: 8px 4px;
          background-color: #fafafa;
          border-radius: 6px;
        "
      >
        <div
          v-for="(item, index) in messages"
          :key="index"
          :style="{
            display: 'flex',
            justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '12px'
          }"
        >
          <div
            :style="{
              maxWidth: '70%',
              padding: '10px 12px',
              borderRadius: '8px',
              backgroundColor: item.role === 'user' ? '#409eff' : '#fff',
              color: item.role === 'user' ? '#fff' : '#333',
              lineHeight: '1.6',
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)'
            }"
          >
            <!-- 当前进行中的一句话 比如「正在查询开放实验室」 -->
            <div
              v-if="item.role === 'assistant' && item.status"
              style="margin-bottom: 6px; font-size: 12px; color: #909399"
            >
              {{ item.status }}
            </div>
            <!-- 本轮已经发生的过程列表 之展示不回传给后端 -->

            <div
              v-if="item.role === 'assistant' && item.steps?.length"
              style="margin-bottom: 8px; font-size: 12px; color: #909399; line-height: 1.5"
            >
              <div v-for="(step, i) in item.steps" :key="i">· {{ step }}</div>
            </div>
            <div v-html="parseMarkdown(item.content)"></div>
            <el-card v-if="item.reservationPreview" shadow="never" style="margin-top: 10px">
              <div style="font-weight: 600; margin-bottom: 8px">预约确认预览</div>
              <div>资源：{{ item.reservationPreview.resource_name || `实验室 #${item.reservationPreview.lab_id}` }}</div>
              <div v-if="item.reservationPreview.equipment_name">设备：{{ item.reservationPreview.equipment_name }}</div>
              <div>日期：{{ item.reservationPreview.date }}</div>
              <div>时间：{{ item.reservationPreview.start_time }}–{{ item.reservationPreview.end_time }}</div>
              <el-button
                type="primary"
                size="small"
                style="margin-top: 10px"
                :loading="item.reservationPreview.confirming"
                :disabled="item.reservationPreview.confirmed"
                @click="confirmPreview(item.reservationPreview)"
              >
                {{ item.reservationPreview.confirmed ? '已提交，等待审核' : '确认并提交预约' }}
              </el-button>
            </el-card>
          </div>
        </div>
      </div>
      <!-- 输入框 -->
      <div style="margin-top: 12px; display: flex; gap: 8px; align-items: flex-end">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          placeholder="问问实验室怎么预约 开放时间等...(Shift + enter换行)"
          @keydown.enter.exact.prevent="handleSend"
          @keydown.enter.left.shift.stop
        >
        </el-input>
        <el-button v-if="!loading" type="primary" @click="handleSend">发送</el-button>
        <el-button v-else type="danger" plain @click="stopStream">停止</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import {
  chatStreamApi,
  confirmReservationApi,
  getConversationMessagesApi,
  listConversationsApi
} from '@/api/ai'
import { ref, reactive, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
const input = ref('')
const loading = ref(false)
const listRef = ref()
const streamController = ref(null)
const conversationId = ref(null)
const conversations = ref([])
const messages = ref([
  {
    role: 'assistant',
    content:
      '您好 我是实验室的助手 你可以向我提问怎么预约 取消 也可以说(帮我预约明天下午的科学实验室) 确认后我会帮你提交'
  }
])

const scrollToBottom = () => {
  nextTick(() => {
    const elem = listRef.value
    if (elem) elem.scrollTop = elem.scrollHeight
  })
}

const handleSend = async () => {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  scrollToBottom()

  // 必须用 reactive：普通对象 push 后再改字段，视图可能不更新
  const assistant = reactive({
    role: 'assistant',
    content: '', // 正文：靠 token 一点点拼
    status: '正在思考…', // 当前状态文案
    steps: [] // 过程流水，不进下次 history
  })
  messages.value.push(assistant)
  streamController.value = new AbortController()

  try {
    // 第二个参数是回调：每解析出一条 SSE 事件就进一次
    await chatStreamApi({
      messages: [{ role: 'user', content: text }],
      conversation_id: conversationId.value
    }, (evt) => {
      if (evt.type === 'status') {
        assistant.status = evt.message || '正在思考…'
      } else if (evt.type === 'tool_start') {
        const label = evt.label || evt.name || '工具'
        assistant.status = `正在${label}…`
        assistant.steps.push(`开始：${label}`)
      } else if (evt.type === 'tool_end') {
        const label = evt.label || evt.name || '工具'
        assistant.status = `${label}完成`
        assistant.steps.push(`完成：${label}`)
        if (evt.preview) {
          assistant.steps.push(`输出结果${evt.preview}`)
        }
      } else if (evt.type === 'token') {
        assistant.content += evt.content || '' // 打字机：追加，不是覆盖
        assistant.status = '' // 开始出字后清掉「正在…」，避免叠在一起
      } else if (evt.type === 'done') {
        assistant.status = ''
        // 注意：不要在这里再 append 一整段正文，否则会双份
      } else if (evt.type === 'error') {
        assistant.status = ''
        if (!assistant.content) {
          assistant.content = evt.message || '请求失败'
        }
        ElMessage.error(evt.message || '请求失败')
      } else if (evt.type === 'reservation_preview') {
        assistant.reservationPreview = { ...evt, confirming: false, confirmed: false }
      } else if (evt.type === 'conversation') {
        conversationId.value = evt.conversation_id
        refreshConversations()
      }
      scrollToBottom()
    }, { signal: streamController.value.signal })
  } catch (err) {
    assistant.status = ''
    if (err.name === 'AbortError') {
      if (!assistant.content) assistant.content = '本次请求已停止。'
      return
    }
    if (!assistant.content) {
      assistant.content = err.message || '网络异常'
    }
    ElMessage.error(err.message || '网络异常')
  } finally {
    loading.value = false
    streamController.value = null
    assistant.status = ''
    scrollToBottom()
  }
}

const stopStream = () => streamController.value?.abort()

const confirmPreview = async (preview) => {
  if (preview.confirming || preview.confirmed) return
  preview.confirming = true
  try {
    await confirmReservationApi(preview.confirmation_token)
    preview.confirmed = true
    ElMessage.success('预约已提交，等待管理员审核')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || err.message || '预约提交失败')
  } finally {
    preview.confirming = false
  }
}

const refreshConversations = async () => {
  try {
    const response = await listConversationsApi()
    conversations.value = response.data || []
  } catch {
    // The active conversation remains usable if its history list is temporarily unavailable.
  }
}

const selectConversation = async (id) => {
  if (!id) return startNewConversation()
  try {
    const response = await getConversationMessagesApi(id)
    conversationId.value = id
    messages.value = (response.data || []).map((item) => ({ ...item, steps: [] }))
    scrollToBottom()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '对话历史加载失败')
  }
}

const startNewConversation = () => {
  conversationId.value = null
  messages.value = [{
    role: 'assistant',
    content: '您好，我是实验室助手。您可以咨询实验室规则、设备和预约流程。'
  }]
}

onMounted(refreshConversations)
// 将 markdown 字符串转换为安全的 HTML 字符串
const parseMarkdown = (text) => {
  if (!text) return ''
  marked.setOptions({ breaks: true }) // 把 \n 转换成 <br>
  // 使用 marked 解析，然后用 DOMPurify 清理
  const rawHtml = marked.parse(text)
  return DOMPurify.sanitize(rawHtml)
}
</script>
