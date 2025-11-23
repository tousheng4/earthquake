<template>
  <el-aside width="360px" class="sidebar">
    <div class="sidebar-content">
      <!-- 统计卡片 -->
      <div class="stats-row">
        <el-card shadow="hover" class="stat-card">
          <template #header>
            <div class="card-header">
              <span>Total</span>
            </div>
          </template>
          <div class="stat-value">{{ filteredQuakes.length }}</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <template #header>
            <div class="card-header">
              <span>Max Mag</span>
            </div>
          </template>
          <div class="stat-value text-danger">{{ maxMagnitude }}</div>
        </el-card>
      </div>

      <!-- 筛选器 -->
      <el-card shadow="hover" class="filter-card">
        <div class="filter-item">
          <span class="label">Min Magnitude: {{ minMag }}</span>
          <el-slider 
            :model-value="minMag"
            @update:model-value="$emit('update:minMag', $event)"
            :min="0" 
            :max="9" 
            :step="0.1" 
            show-input 
            size="small" 
          />
        </div>
      </el-card>

      <!-- 列表 -->
      <div class="list-container">
        <div class="list-header">Recent Earthquakes</div>
        <el-scrollbar>
          <ul class="quake-list">
            <li
              v-for="quake in filteredQuakes"
              :key="quake.id || quake.time"
              class="quake-item"
              @click="$emit('quake-selected', quake)"
            >
              <div class="quake-mag" :style="{ backgroundColor: getColorByMagnitude(quake.magnitude) }">
                {{ quake.magnitude.toFixed(1) }}
              </div>
              <div class="quake-info">
                <div class="quake-region">{{ quake.region }}</div>
                <div class="quake-time">{{ formatTime(quake.time) }}</div>
              </div>
            </li>
          </ul>
        </el-scrollbar>
      </div>
    </div>
  </el-aside>
</template>

<script setup>
import { computed } from 'vue';
import { getColorByMagnitude, formatTime } from '../utils/formatters';

const props = defineProps({
  filteredQuakes: {
    type: Array,
    default: () => []
  },
  minMag: {
    type: Number,
    default: 2.5
  }
});

defineEmits(['update:minMag', 'quake-selected']);

const maxMagnitude = computed(() => {
  if (props.filteredQuakes.length === 0) return 0;
  return Math.max(...props.filteredQuakes.map((q) => q.magnitude)).toFixed(1);
});
</script>

<style scoped>
.sidebar {
  background-color: #0d1b2a;
  border-right: 1px solid #1f2d3d;
  display: flex;
  flex-direction: column;
}

.sidebar-content {
  padding: 15px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stats-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.stat-card {
  background-color: #162438;
  border: 1px solid #2c3e50;
  color: #fff;
}
.stat-card :deep(.el-card__header) {
  padding: 10px;
  border-bottom: 1px solid #2c3e50;
}
.stat-card :deep(.el-card__body) {
  padding: 15px;
  text-align: center;
}

.card-header {
  font-size: 12px;
  color: #909399;
  text-transform: uppercase;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}
.text-danger {
  color: #f56c6c;
}

.filter-card {
  background-color: #162438;
  border: 1px solid #2c3e50;
  color: #fff;
}
.filter-card :deep(.el-card__body) {
  padding: 15px;
}

.filter-item .label {
  display: block;
  margin-bottom: 5px;
  font-size: 14px;
  color: #ccc;
}

.list-container {
  flex: 1;
  background-color: #162438;
  border: 1px solid #2c3e50;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  padding: 10px 15px;
  background-color: #1f2d3d;
  font-weight: bold;
  font-size: 14px;
  border-bottom: 1px solid #2c3e50;
}

.quake-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.quake-item {
  display: flex;
  align-items: center;
  padding: 10px 15px;
  border-bottom: 1px solid #2c3e50;
  cursor: pointer;
  transition: background-color 0.2s;
}

.quake-item:hover {
  background-color: #2a3b55;
}

.quake-mag {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: #fff;
  margin-right: 12px;
  font-size: 14px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

.quake-info {
  flex: 1;
  overflow: hidden;
}

.quake-region {
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.quake-time {
  font-size: 12px;
  color: #909399;
}
</style>
