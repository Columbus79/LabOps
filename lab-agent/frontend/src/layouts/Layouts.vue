<template>
  <div>
    <el-container style="min-height: 100vh">
      <el-header
        style="
          display: flex;
          align-items: center;
          border-bottom: 1px solid #eee;
          background-color: #fff;
        "
      >
        <div
          style="flex: 1; display: flex; align-items: center; font-size: 24px; font-weight: bold"
        >
          <img
            style="width: 40px; height: 40px; margin-right: 10px"
            src="../assets/imgs/logo.png"
            alt=""
          />
          <div style="margin-left: 5px">LabOps 实验室运营平台</div>
        </div>
        <div style="display: flex; align-items: center">
          <el-badge :value="unreadCount" :hidden="unreadCount === 0" style="margin-right: 20px">
            <el-button circle @click="router.push('/manager/notifications')" aria-label="站内通知">
              <el-icon><Bell /></el-icon>
            </el-button>
          </el-badge>
          <el-dropdown @command="handleCommand">
            <div style="display: flex; align-items: center; cursor: pointer">
              <img
                v-if="userInfo?.avatar"
                :src="userInfo.avatar"
                alt="用户头像"
                style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover"
              />
              <div style="margin-left: 3px">{{ userInfo.name }}</div>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-container>
        <el-aside width="220px">
          <el-menu
            router
            :default-active="router.currentRoute.value.path"
            style="height: 100%"
            default-active="/manager/home"
          >
            <el-menu-item index="/manager/home">
              <el-icon><icon-menu /></el-icon>
              <span>系统首页</span>
            </el-menu-item>
            <el-menu-item index="/manager/ai-chat">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI智能助手</span>
            </el-menu-item>
            <el-menu-item index="/manager/notifications">
              <el-icon><Bell /></el-icon>
              <span>站内通知</span>
              <el-badge v-if="unreadCount" :value="unreadCount" style="margin-left: auto" />
            </el-menu-item>
            <el-menu-item index="/manager/maintenance">
              <el-icon><Tools /></el-icon>
              <span>{{ userInfo?.role === 'admin' ? '维修工单处理' : '设备故障申报' }}</span>
            </el-menu-item>
            <el-menu-item index="/manager/lablist" v-if="userInfo?.role === 'student'">
              <el-icon><OfficeBuilding /></el-icon>
              <span>实验室列表</span>
            </el-menu-item>
            <el-menu-item index="/manager/my-reservation" v-if="userInfo?.role === 'student'">
              <el-icon><Tickets /></el-icon>
              <span>我的预约</span>
            </el-menu-item>
            <el-menu-item index="/manager/lab" v-if="userInfo?.role === 'admin'">
              <el-icon><House /></el-icon>
              <span>实验室管理</span>
            </el-menu-item>
            <el-menu-item index="/manager/equipment" v-if="userInfo?.role === 'admin'">
              <el-icon><Setting /></el-icon>
              <span>设备管理</span>
            </el-menu-item>
            <el-menu-item index="/manager/audit-reservation" v-if="userInfo?.role === 'admin'">
              <el-icon><DocumentChecked /></el-icon>
              <span>预约审核</span>
            </el-menu-item>
            <el-menu-item index="/manager/operations" v-if="userInfo?.role === 'admin'">
              <el-icon><DataAnalysis /></el-icon>
              <span>运营分析</span>
            </el-menu-item>
            <el-menu-item index="/manager/user" v-if="userInfo?.role === 'admin'">
              <el-icon><user /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { logout } from '@/utils/auth'
import { useUser } from '@/utils/user'
import {
  Document,
  Menu as IconMenu,
  Location,
  Setting,
  User,
  House,
  OfficeBuilding,
  Tickets,
  DocumentChecked,
  ChatDotRound,
  Bell,
  Tools,
  DataAnalysis
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { getUnreadCount } from '@/api/operations'
import router from '@/router'

const { userInfo } = useUser()
const unreadCount = ref(0)
const refreshUnread = async () => {
  try {
    const result = await getUnreadCount()
    unreadCount.value = result.data?.count || 0
  } catch {
    unreadCount.value = 0
  }
}
const onNotificationsUpdated = () => refreshUnread()

onMounted(() => {
  refreshUnread()
  window.addEventListener('notifications-updated', onNotificationsUpdated)
})
onBeforeUnmount(() => window.removeEventListener('notifications-updated', onNotificationsUpdated))
watch(() => router.currentRoute.value.path, refreshUnread)

const handleCommand = (command) => {
  if (command === 'profile') {
    router.push('/manager/profile')
  } else if (command === 'logout') {
    logout()
    router.push('/login')
    ElMessage.success('退出登录成功')
  } else if (command === 'password') {
    router.push('/manager/password')
  }
}
</script>
