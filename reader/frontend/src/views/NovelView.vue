<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const novel = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const res = await fetch(`/api/novels/${route.params.id}`)
    if (!res.ok) throw new Error('Novel not found')
    novel.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function chapterLabel(filename) {
  // chapter_001.txt → Chapter 1
  const m = filename.match(/(\d+)/)
  return m ? `Chapter ${parseInt(m[1])}` : filename.replace('.txt', '')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="max-w-3xl mx-auto px-4 py-4 flex items-center gap-3">
        <button @click="router.push('/')" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors">
          ← Back
        </button>
        <span class="text-gray-300 dark:text-gray-600">|</span>
        <span class="text-gray-600 dark:text-gray-300 truncate text-sm">{{ novel ? (novel.title_translated || novel.title) : '...' }}</span>
      </div>
    </header>

    <main class="max-w-3xl mx-auto px-4 py-8">
      <div v-if="loading" class="flex justify-center py-20">
        <div class="w-8 h-8 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <div v-else-if="error" class="text-center py-20 text-red-500">{{ error }}</div>

      <template v-else-if="novel">
        <!-- Novel info -->
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-0.5">{{ novel.title_translated || novel.title }}</h1>
          <p v-if="novel.title_translated && novel.title_translated !== novel.title" class="text-sm text-gray-400 dark:text-gray-500 mb-1">{{ novel.title }}</p>
          <p v-if="novel.author" class="text-gray-500 dark:text-gray-400 mb-3">{{ novel.author }}</p>
          <div class="flex flex-wrap gap-2 text-sm mb-4">
            <span class="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-3 py-1 rounded-full">
              {{ novel.source_language }} → {{ novel.target_language }}
            </span>
            <span class="bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 px-3 py-1 rounded-full">
              {{ novel.chapters.length }}{{ novel.total_chapters ? ` / ${novel.total_chapters}` : '' }} chapters
            </span>
          </div>
          <p v-if="novel.synopsis" class="text-gray-600 dark:text-gray-300 leading-relaxed">{{ novel.synopsis }}</p>
        </div>

        <!-- Chapter list -->
        <div v-if="novel.chapters.length === 0" class="text-center py-10 text-gray-400">
          No translated chapters yet.
        </div>

        <div v-else class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700">
          <button
            v-for="ch in novel.chapters"
            :key="ch"
            @click="router.push(`/novel/${novel.id}/chapter/${ch}`)"
            class="w-full text-left px-5 py-3 text-gray-700 dark:text-gray-300 hover:bg-violet-50 dark:hover:bg-violet-900/20 hover:text-violet-700 dark:hover:text-violet-300 transition-colors text-sm"
          >
            {{ chapterLabel(ch) }}
          </button>
        </div>
      </template>
    </main>
  </div>
</template>
