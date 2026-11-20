import { getToken, logout } from '@/utils/auth'
import request from '@/utils/request'
import router from '@/router'

export function confirmReservationApi(token) {
  return request({ url: '/api/ai/reservations/confirm', method: 'post', data: { token } })
}

export function listConversationsApi() {
  return request({ url: '/api/ai/conversations', method: 'get' })
}

export function createConversationApi() {
  return request({ url: '/api/ai/conversations', method: 'post' })
}

export function getConversationMessagesApi(id) {
  return request({ url: `/api/ai/conversations/${id}/messages`, method: 'get' })
}

export async function chatStreamApi(data, onEvent, { signal } = {}) {
  const configuredBase = import.meta.env.VITE_API_BASE_URL || ''
  const baseUrl = configuredBase.replace(/\/+$/, '')
  const token = getToken()
  const response = await fetch(`${baseUrl}/api/ai/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(data),
    signal
  })

  if (response.status === 401) {
    logout()
    await router.replace('/login')
    throw new Error('登录已失效，请重新登录')
  }
  if (!response.ok || !response.body) {
    let message = `流式请求失败 (${response.status})`
    try {
      const payload = await response.json()
      message = payload.message || payload.detail || message
    } catch {}
    throw new Error(message)
  }
  if (!(response.headers.get('content-type') || '').toLowerCase().includes('text/event-stream')) {
    throw new Error('服务器返回的内容不是 SSE 流')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let finished = false
  const dispatch = (frame) => {
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
      .join('\n')
    if (!data) return false
    if (data.trim() === '[DONE]') return true
    onEvent(JSON.parse(data))
    return false
  }

  try {
    while (!finished) {
      const { done, value } = await reader.read()
      if (done) {
        buffer += decoder.decode()
      } else {
        buffer += decoder.decode(value, { stream: true })
      }
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() || ''
      for (const frame of frames) {
        if (dispatch(frame)) {
          finished = true
          break
        }
      }
      if (done) {
        if (buffer.trim()) dispatch(buffer)
        break
      }
    }
  } finally {
    if (signal?.aborted) await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
