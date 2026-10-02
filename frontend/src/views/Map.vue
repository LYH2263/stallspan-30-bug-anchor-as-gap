<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const vendors = ref<any[]>([])
async function run() { data.value = await api('/allocate/run?segment_id=1', { method: 'POST' }) }
onMounted(async () => {
  vendors.value = await api('/vendors')
  await run()
})
const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']
const cells = computed(() => {
  if (!data.value) return []
  const width = data.value.segment.width_m
  const out: any[] = []
  for (const p of data.value.pillars || []) {
    out.push({ type: 'pillar', start: p.position_m - p.thickness_m/2, w: p.thickness_m, label: p.label || '挡柱' })
  }
  // 色块只来自后端 placements：越出容差带的摊已在后端被剔除，图上绝不会画出越界色块。
  for (const [i, p] of (data.value.placements || []).entries()) {
    out.push({ type: 'stall', start: p.start_m, w: p.width_m, label: p.vendor_name, color: colors[i % colors.length] })
  }
  return out.sort((a,b) => a.start - b.start).map(c => ({ ...c, pct: Math.max((c.w / width) * 100, 2) }))
})
// 锚点容差带：区间取自后端 anchor_bands（与落位/拒绝同一套判定）。
const bands = computed(() => {
  if (!data.value) return []
  const width = data.value.segment.width_m
  return (data.value.anchor_bands || []).map((b: any) => ({
    ...b,
    leftPct: (b.band_start_m / width) * 100,
    widthPct: Math.max(((b.band_end_m - b.band_start_m) / width) * 100, 0.6),
    centerPct: (b.anchor_m / width) * 100,
  }))
})
function anchorText(v: any) {
  return v.anchor_m === null || v.anchor_m === undefined ? '' : `锚点 ${v.anchor_m}±${v.anchor_tolerance_m ?? 0} m`
}
</script>
<template>
  <div class="ss-street-wrap">
    <h1>街段分配带</h1>
    <p class="sub">沿街一维开间 · 挡柱为竖直阻断 · 虚线框为锚点容差带，起点必须落在带内且不跨柱</p>
    <button class="btn" @click="run">重新分配</button>
    <div class="ss-band-ruler" v-if="data">
      <span>0 m</span>
      <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
      <span>{{ data.segment.width_m }} m</span>
    </div>
    <div class="ss-street-band" v-if="data">
      <!-- 容差带覆盖层：与色块使用同一米标→百分比投影，区间来自后端判定 -->
      <div
        v-for="b in bands" :key="'band-' + b.vendor_id"
        class="ss-anchor-band"
        :style="{ left: b.leftPct + '%', width: b.widthPct + '%' }"
      >
        <span class="ss-anchor-center" :style="{ left: (b.centerPct - b.leftPct) / b.widthPct * 100 + '%' }"></span>
      </div>
      <div class="ss-street-inner">
        <div
          v-for="(c,i) in cells" :key="i"
          class="ss-band-cell"
          :class="{ 'ss-pillar': c.type === 'pillar' }"
          :style="{ width: c.pct + '%', background: c.type === 'pillar' ? undefined : c.color, flex: '0 0 ' + c.pct + '%' }"
        >{{ c.label }}</div>
      </div>
    </div>
    <div class="ss-vendor-queue">
      <div v-for="v in vendors" :key="v.id" class="ss-vendor-chip">
        <strong>{{ v.name }}</strong>
        <span>需 {{ v.stall_width_m }} m · 优先 {{ v.priority }}</span>
        <span v-if="anchorText(v)">{{ anchorText(v) }}</span>
      </div>
    </div>
    <div class="card" v-if="data">
      <table>
        <thead><tr><th>摊主</th><th>起点</th><th>终点</th><th>宽度</th><th>锚点带</th></tr></thead>
        <tbody>
          <tr v-for="p in data.placements" :key="p.vendor_id">
            <td>{{ p.vendor_name }}</td><td>{{ p.start_m }}</td><td>{{ p.end_m }}</td><td>{{ p.width_m }}</td>
            <td v-if="p.anchor_m !== null && p.anchor_m !== undefined">
              {{ p.anchor_m - p.anchor_tolerance_m }}～{{ p.anchor_m + p.anchor_tolerance_m }}
            </td>
            <td v-else class="muted">—</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
