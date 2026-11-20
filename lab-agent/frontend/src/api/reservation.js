import request from '@/utils/request'

/**
 * student端创建预约请求
 */

export function createReservationApi(data) {
  return request({
    url: '/api/reservation',
    method: 'post',
    data
  })
}
/**
 * student查询预约记录
 * @param {page, pageList, status} params
 * @returns
 */
export function getReservationPageList(params) {
  return request({
    url: '/api/reservation/list',
    method: 'get',
    params
  })
}
/**
 * student取消预约
 * @param {int} reservation_id
 * @returns
 */
export function cancelReservationApi(reservation_id) {
  return request({
    url: `/api/reservation/${reservation_id}/cancel`,
    method: 'put'
  })
}
export const checkInReservationApi = (id) => request({ url: `/api/reservation/${id}/check-in`, method: 'put' })
export const checkOutReservationApi = (id) => request({ url: `/api/reservation/${id}/check-out`, method: 'put' })
export const resolveReservationApi = (id, data) => request({ url: `/api/reservation/${id}/resolve`, method: 'put', data })
/**
 * 
 * @param {*} reservation_id 
 * @param {*} status 
 * @returns 
 */
export function auditReservationApi(reservation_id, status) {
  return request({
    url: `/api/reservation/${reservation_id}/audit`,
    method: 'put',
    data: {status}
  })
}
