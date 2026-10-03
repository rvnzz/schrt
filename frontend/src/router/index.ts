import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import GroupsView from '@/views/GroupsView.vue'
import GroupDetailView from '@/views/GroupDetailView.vue'
import AssignmentsView from '@/views/AssignmentsView.vue'
import AssignmentDetailView from '@/views/AssignmentDetailView.vue'
import SubmitView from '@/views/SubmitView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/groups' },
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/groups', name: 'groups', component: GroupsView },
    { path: '/groups/:id', name: 'group-detail', component: GroupDetailView },
    { path: '/assignments', name: 'assignments', component: AssignmentsView },
    { path: '/assignments/:id', name: 'assignment-detail', component: AssignmentDetailView },
    { path: '/s/:code', name: 'submit', component: SubmitView, meta: { public: true } },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return '/login'
  }
})

export default router
