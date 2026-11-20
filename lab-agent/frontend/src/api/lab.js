import request from '@/utils/request'

/** admin才可以进行如下操作 */

/**
 * 分页式查询实验室信息
 */
export function getLabPageList(params) {
  return request({
    url: '/api/lab/list',
    method: 'get',
    params
  })
}

/**
 * 
 * 根据lab_id查询具体实验室
 * @param {Number} labId 
 * @returns 
 */
export function getLab(labId) {
  return request({
    url: `/api/lab/${labId}`,
    method: 'get'
  })
}

/**
 * 创建实验室
 */
export function createLabApi(data) {
  return request({
    url: '/api/lab',
    method: 'post',
    data
  })
}

/**
 * 更新实验室信息
 */
export function updateLabApi(labId, data) {
  return request({
    url: `/api/lab/${labId}`,
    method: 'put',
    data
  })
}

/**
 * 删除实验室
 */
export function deleteLabApi(labId) {
  return request({
    url: `/api/lab/${labId}`,
    method: 'delete'
  })
}
