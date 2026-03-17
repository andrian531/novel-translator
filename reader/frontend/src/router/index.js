import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import NovelView from '../views/NovelView.vue'
import ChapterView from '../views/ChapterView.vue'

const routes = [
  { path: '/', component: HomeView },
  { path: '/novel/:id', component: NovelView },
  { path: '/novel/:id/chapter/:filename', component: ChapterView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})
