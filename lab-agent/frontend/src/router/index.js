import { getToken, getUserInfo } from '@/utils/auth'
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/manager/home' },
    {
      path: '/manager',
      name: 'Layout',
      component: () => import('@/layouts/Layouts.vue'),
      children: [
        { path: 'home', name: 'Home', component: () => import('@/views/Home.vue') },
        { path: 'lab', name: 'Lab', component: () => import('@/views/Lab.vue'), meta: { roles: ['admin'] } },
        { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue') },
        { path: 'password', name: 'Password', component: () => import('@/views/Password.vue') },
        { path: 'user', name: 'User', component: () => import('@/views/Users.vue'), meta: { roles: ['admin'] } },
        { path: 'equipment', name: 'Equipment', component: () => import('@/views/Equipment.vue'), meta: { roles: ['admin'] } },
        { path: 'lablist', name: 'LabList', component: () => import('@/views/LabList.vue'), meta: { roles: ['student'] } },
        {
          path: 'lab-equipment',
          name: 'LabEquipment',
          component: () => import('@/views/LabEquipment.vue'),
          meta: { roles: ['student'] }
        },
        {
          path: 'my-reservation',
          name: 'MyReservation',
          component: () => import('@/views/MyReservation.vue'),
          meta: { roles: ['student'] }
        },
        {
          path: 'audit-reservation',
          name: 'AuditReservation',
          component: () => import('@/views/AuditReservation.vue'),
          meta: { roles: ['admin'] }
        },
        {
          path: 'ai-chat',
          name: 'AIChat',
          component: () => import('@/views/AIChat.vue')
        },
        { path: 'notifications', name: 'Notifications', component: () => import('@/views/Notifications.vue') },
        { path: 'maintenance', name: 'Maintenance', component: () => import('@/views/Maintenance.vue') },
        { path: 'operations', name: 'Operations', component: () => import('@/views/Operations.vue'), meta: { roles: ['admin'] } },
      ]
    },

    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') }
  ]
})

// 路由守卫 验证token
router.beforeEach((to, from) => {
  const token = getToken()
  if (to.path === '/login' || to.path === '/register') {
    return true
  } else if (!token) {
    return '/login'
  } else {
    const roles = to.meta.roles
    const user = getUserInfo()
    if (roles?.length && !roles.includes(user?.role)) return '/manager/home'
    return true
  }
})
export default router
