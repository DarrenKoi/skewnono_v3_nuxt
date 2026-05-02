/**
 * router/index.js
 *
 * Manual route configuration
 */

import { createRouter, createWebHistory } from 'vue-router'
import MainPage from '@/pages/MainPage.vue'
import ResultPage from '@/pages/ResultPage.vue'
import DataTrendPage from '@/pages/DataTrendPage.vue'
import AboutPage from '@/pages/AboutPage.vue'
import ContactPage from '@/pages/ContactPage.vue'

const routes = [
  {
    path: '/',
    name: 'MainPage',
    component: MainPage
  },
  {
    path: '/about',
    name: 'AboutPage',
    component: AboutPage
  },
  {
    path: '/contact',
    name: 'ContactPage',
    component: ContactPage
  },
  {
    path: '/result/:recipeId/:filename',
    name: 'ResultPage',
    component: ResultPage,
    props: true,
    beforeEnter: (to, from, next) => {
      // Validate required parameters
      const { recipeId, filename } = to.params
      
      if (!recipeId || !filename) {
        console.error('Missing required parameters for ResultPage:', { recipeId, filename })
        // Redirect to main page if parameters are missing
        next('/')
        return
      }
      
      // Decode parameters to ensure they're properly handled
      try {
        to.params.filename = decodeURIComponent(filename)
        to.params.recipeId = decodeURIComponent(recipeId)
        next()
      } catch (error) {
        console.error('Error decoding route parameters:', error)
        next('/')
      }
    }
  },
  {
    path: '/result/data_trend',
    name: 'DataTrendPage',
    component: DataTrendPage
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
