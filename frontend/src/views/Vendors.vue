<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const saving = ref<number | null>(null)
const savedId = ref<number | null>(null)

onMounted(load)
async function load() {
  rows.value = await api('/vendors')
  drafts.value = {}
  for (const r of rows.value) drafts.value[r.id] = draft(r)
}

// 本地草稿：锚点留空表示“无锚点”，按从左填法。
function draft(r: any) {
  return {
    anchor: r.anchor_m === null || r.anchor_m === undefined ? '' : String(r.anchor_m),
    tol: r.anchor_tolerance_m === null || r.anchor_tolerance_m === undefined ? '0' : String(r.anchor_tolerance_m),
  }
}
const drafts = ref<Record<number, { anchor: string; tol: string }>>({})

async function save(r: any) {
  const d = drafts.value[r.id]
  const anchorRaw = d.anchor.trim()
  // 非法输入在发请求前整单打回：不改本地已保存值、不发 PATCH，
  // 图与“放不下”名单自然停留在改前那次分配结果。
  if (anchorRaw !== '') {
    const anchor = Number(anchorRaw)
    const tol = Number(d.tol.trim() || '0')
    if (!Number.isFinite(anchor) || anchor < 0) {
      alert('期望锚点米标非法：须填不小于 0 的数字（留空表示无锚点）')
      return
    }
    if (!Number.isFinite(tol) || tol < 0) {
      alert('容差非法：须填不小于 0 的数字')
      return
    }
  }
  const payload =
    anchorRaw === ''
      ? { anchor_m: null, anchor_tolerance_m: null }
      : { anchor_m: Number(anchorRaw), anchor_tolerance_m: Number(d.tol.trim() || '0') }
  saving.value = r.id
  try {
    const updated = await api(`/vendors/${r.id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    const idx = rows.value.findIndex((x) => x.id === r.id)
    if (idx >= 0) rows.value[idx] = updated
    drafts.value[r.id] = draft(updated)
    savedId.value = r.id
    setTimeout(() => { if (savedId.value === r.id) savedId.value = null }, 1500)
  } catch (e: any) {
    alert('保存失败：' + e.message)
  } finally {
    saving.value = null
  }
}
</script>
<template>
  <h1>摊主队列</h1>
  <p class="sub">底部排队条 · 宽度与优先级 · 可登记期望锚点米标与容差（起点须落在锚点 ± 容差内）</p>
  <div class="ss-vendor-queue" style="border-top:none; background:transparent; margin:0; padding:0.5rem 0 1rem">
    <div v-for="r in rows" :key="r.id" class="ss-vendor-chip">
      <strong>{{ r.name }}</strong>
      <span>需 {{ r.stall_width_m }} m · 优先 {{ r.priority }}</span>
      <span v-if="r.anchor_m !== null && r.anchor_m !== undefined">
        锚点 {{ r.anchor_m }}±{{ r.anchor_tolerance_m ?? 0 }} m
      </span>
    </div>
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th>摊主</th><th>宽度(m)</th><th>优先级</th><th>期望锚点(m)</th><th>容差(±m)</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.name }}</td>
          <td>{{ r.stall_width_m }}</td>
          <td>{{ r.priority }}</td>
          <td>
            <input
              v-model="drafts[r.id].anchor"
              type="number" step="0.1" min="0" placeholder="无锚点"
              style="width:6.5rem"
            />
          </td>
          <td>
            <input
              v-model="drafts[r.id].tol"
              type="number" step="0.1" min="0" placeholder="0"
              style="width:5rem"
            />
          </td>
          <td>
            <button class="btn" style="padding:0.25rem 0.6rem" :disabled="saving === r.id" @click="save(r)">
              {{ saving === r.id ? '保存中' : (savedId === r.id ? '已保存' : '保存') }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="muted" style="margin-bottom:0">锚点留空即无锚点，仍按从左填法；设置后重跑分配，起点须落在容差带内，对不上则进“放不下”。</p>
  </div>
</template>
