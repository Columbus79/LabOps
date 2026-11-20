import request from '@/utils/request'

export const getDashboardSummary = () => request({ url: '/api/dashboard/summary', method: 'get' })
export const getOperationsReport = (params) => request({ url: '/api/dashboard/operations', method: 'get', params })
export const getNotifications = (params) => request({ url: '/api/notifications', method: 'get', params })
export const getUnreadCount = () => request({ url: '/api/notifications/unread-count', method: 'get' })
export const markNotificationRead = (id) => request({ url: `/api/notifications/${id}/read`, method: 'put' })
export const markAllNotificationsRead = () => request({ url: '/api/notifications/read-all', method: 'put' })
export const getMaintenanceTickets = (params) => request({ url: '/api/maintenance', method: 'get', params })
export const getUntrackedMaintenanceEquipment = () => request({ url: '/api/maintenance/untracked', method: 'get' })
export const reportMaintenance = (data) => request({ url: '/api/maintenance', method: 'post', data })
export const updateMaintenance = (id, data) => request({ url: `/api/maintenance/${id}`, method: 'put', data })
