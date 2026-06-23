<template>
  <router-view />
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue'

// 全局遮罩看门狗（不依赖路由）：
// 弹窗已全部 teleported=false，body 上正常只应有「打开中的 ElMessageBox(含 .el-message-box)」。
// 其余 body 级 .el-overlay / 全屏 loading 都是组件卸载后残留的孤儿遮罩——它们透明却拦截所有点击，
// 导致点侧栏切不动（点击被吞→路由不切→挂在路由上的清理永远不触发，死锁）。
// 定时移除孤儿遮罩即可彻底破解，且不会误删打开中的弹窗。
let _timer = null
function killOrphanOverlays() {
  document.querySelectorAll('body > .el-overlay').forEach((ov) => {
    if (!ov.querySelector('.el-message-box')) ov.remove()
  })
  document.querySelectorAll('body > .el-loading-mask, .el-loading-mask.is-fullscreen').forEach((m) => m.remove())
}

onMounted(() => { _timer = setInterval(killOrphanOverlays, 700) })
onBeforeUnmount(() => { if (_timer) clearInterval(_timer) })
</script>
