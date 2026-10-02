<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
onMounted(async () => {
  const data = await api('/allocate/latest?segment_id=1')
  // 与主图同源：rejected 由后端按同一套空档/容差带判定产出。
  rows.value = data.rejected || []
})
function bandText(r: any) {
  if (r.anchor_m === null || r.anchor_m === undefined) return '—'
  const tol = r.anchor_tolerance_m ?? 0
  return `${r.anchor_m - tol}～${r.anchor_m + tol} m`
}
</script>
<template>
  <h1>放不下</h1>
  <p class="sub">无法在连续空档内安置且不跨越挡柱的摊位 · 原因与主图起点同一条容差带判定</p>
  <div class="card">
    <table>
      <thead><tr><th>摊主</th><th>需求宽度</th><th>锚点容差带</th><th>原因</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.vendor_id">
          <td>{{ r.vendor_name }}</td><td>{{ r.width_m }}</td><td>{{ bandText(r) }}</td><td>{{ r.reason }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!rows.length" class="muted">全部放下</p>
  </div>
</template>
