<template>
  <el-header class="header">
    <div class="logo">
      <el-icon :size="24" class="logo-icon"><Odometer /></el-icon>
      <span>Global Earthquake Monitor</span>
    </div>
    <div class="header-right">
      <el-switch
        :model-value="showPlates"
        @update:model-value="$emit('update:showPlates', $event)"
        active-text="Plates"
        inactive-text="Hide"
        inline-prompt
        style="margin-right: 15px; --el-switch-on-color: #f56c6c; --el-switch-off-color: #909399"
      />
      <el-radio-group 
        :model-value="mapStyle" 
        @update:model-value="$emit('update:mapStyle', $event)"
        size="small" 
        style="margin-right: 15px"
      >
        <el-radio-button label="dark">Dark</el-radio-button>
        <el-radio-button label="light">Light</el-radio-button>
        <el-radio-button label="terrain">Terrain</el-radio-button>
      </el-radio-group>
      <el-switch
        :model-value="isHeatmapMode"
        @update:model-value="$emit('update:isHeatmapMode', $event)"
        active-text="Heatmap"
        inactive-text="Scatter"
        inline-prompt
        style="margin-right: 15px; --el-switch-on-color: #e6a23c; --el-switch-off-color: #409eff"
      />
      <el-tag type="success" effect="dark" round>Live Data</el-tag>
      <span class="time">{{ currentTime }}</span>
    </div>
  </el-header>
</template>

<script setup>
defineProps({
  showPlates: Boolean,
  mapStyle: String,
  isHeatmapMode: Boolean,
  currentTime: String
});

defineEmits(['update:showPlates', 'update:mapStyle', 'update:isHeatmapMode']);
</script>

<style scoped>
.header {
  background-color: #0a1625;
  border-bottom: 1px solid #1f2d3d;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 60px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: bold;
  color: #409eff;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.time {
  font-family: monospace;
  color: #909399;
  font-size: 14px;
}
</style>
