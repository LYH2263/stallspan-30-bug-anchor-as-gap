<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
onMounted(async () => { rows.value = await api('/pillars') })
</script>
<template>
  <h1>挡柱</h1>
  <p class="sub">街段障碍 · 在分配带上表现为竖直阻断块</p>
  <div class="ss-street-band" style="height:90px;min-height:90px">
    <div class="ss-street-inner" style="gap:1rem;padding:0 1rem;align-items:center">
      <div
        v-for="r in rows" :key="r.id ?? JSON.stringify(r)"
        class="ss-band-cell ss-pillar"
        :style="{ width: Math.max(r.thickness_m * 28, 36) + 'px', flex: '0 0 auto', height: '70%' }"
      >{{ r.label }} @{{ r.position_m }}m</div>
    </div>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>名称</th><th>位置(m)</th><th>厚度(m)</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)"><td>{{ r.label }}</td><td>{{ r.position_m }}</td><td>{{ r.thickness_m }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
