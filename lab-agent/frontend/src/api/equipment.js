import request from '@/utils/request'

/**  admin才可以进新如下操作 */

/**
 * admin根据keywords进行分页式查询数据库 获取实验室设备列表
 */

export function getEquipmentPageList(params) {
  return request({
    url: '/api/equipment/list',
    method: 'get',
    params
  })
}

/**
 * 创建实验室设备
 */
export function createEquipmentApi(data) {
  return request({
    url: '/api/equipment',
    method: 'post',
    data
  })
}

/**
 * 更新实验室设备信息
 */
export function updateEquipmentApi(equipment_id, data) {
  return request({
    url: `/api/equipment/${equipment_id}`,
    method: 'put',
    data
  })
}

/**
 * 删除实验室设备
 */
export function deleteEquipmentApi(equipment_id) {
  return request({
    url: `/api/equipment/${equipment_id}`,
    method: 'delete'
  })
}
