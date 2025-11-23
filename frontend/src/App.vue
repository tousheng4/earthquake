<template>
  <el-container class="layout-container">
    <el-header class="header">
      <div class="logo">
        <el-icon :size="24" class="logo-icon"><Odometer /></el-icon>
        <span>Global Earthquake Monitor</span>
      </div>
      <div class="header-right">
        <el-switch
          v-model="isHeatmapMode"
          active-text="Heatmap (Density)"
          inactive-text="Scatter (Events)"
          inline-prompt
          style="margin-right: 15px; --el-switch-on-color: #e6a23c; --el-switch-off-color: #409eff"
        />
        <el-tag type="success" effect="dark" round>Live Data</el-tag>
        <span class="time">{{ currentTime }}</span>
      </div>
    </el-header>

    <el-container class="main-content">
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
              <el-slider v-model="minMag" :min="0" :max="9" :step="0.1" show-input size="small" />
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
                  @click="focusOnQuake(quake)"
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

      <el-main class="map-container">
        <div ref="chartRef" class="chart"></div>
        
        <!-- 地图图例 (GIS Element) -->
        <div class="map-legend" v-if="!isHeatmapMode">
          <div class="legend-title">Magnitude Scale</div>
          <div class="legend-item"><span class="color-box" style="background: #4caf50"></span> &lt; 3.0 (Minor)</div>
          <div class="legend-item"><span class="color-box" style="background: #ffeb3b"></span> 3.0 - 4.5 (Light)</div>
          <div class="legend-item"><span class="color-box" style="background: #ff9800"></span> 4.5 - 6.0 (Moderate)</div>
          <div class="legend-item"><span class="color-box" style="background: #f44336"></span> &gt; 6.0 (Strong)</div>
        </div>

        <div class="loading-mask" v-if="loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>Loading Data...</span>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from "vue";
import * as echarts from "echarts";
import axios from "axios";
import dayjs from "dayjs";

// --- 状态 ---
const chartRef = ref(null);
let chartInstance = null;
const earthquakes = ref([]);
const loading = ref(true);
const currentTime = ref(dayjs().format("YYYY-MM-DD HH:mm:ss"));
const minMag = ref(2.5); // 默认过滤掉小地震
const isHeatmapMode = ref(false); // GIS: 切换可视化模式
let timerId = null;
let clockId = null;

const BACKEND_BASE_URL = "http://127.0.0.1:5000";

// --- 计算属性 ---
const filteredQuakes = computed(() => {
  return earthquakes.value
    .filter((q) => q.magnitude >= minMag.value)
    .sort((a, b) => new Date(b.time) - new Date(a.time));
});

const maxMagnitude = computed(() => {
  if (filteredQuakes.value.length === 0) return 0;
  return Math.max(...filteredQuakes.value.map((q) => q.magnitude)).toFixed(1);
});

// --- 辅助函数 ---
function getColorByMagnitude(mag) {
  if (mag < 3.0) return "#4caf50"; // Green
  if (mag < 4.5) return "#ffeb3b"; // Yellow
  if (mag < 6.0) return "#ff9800"; // Orange
  return "#f44336";               // Red
}

function formatTime(timeStr) {
  return dayjs(timeStr).format("MM-DD HH:mm");
}

// GIS: 格式化经纬度显示
function formatCoordinate(lon, lat) {
  const lonStr = Math.abs(lon).toFixed(2) + "°" + (lon >= 0 ? "E" : "W");
  const latStr = Math.abs(lat).toFixed(2) + "°" + (lat >= 0 ? "N" : "S");
  return `${latStr}, ${lonStr}`;
}

// --- ECharts 逻辑 ---
async function loadWorldMap() {
  try {
    const res = await axios.get("/world.json");
    echarts.registerMap("world", res.data);
  } catch (error) {
    console.error("Failed to load world map:", error);
  }
}

async function fetchEarthquakes() {
  try {
    const res = await axios.get(`${BACKEND_BASE_URL}/earthquakes`);
    earthquakes.value = res.data;
    loading.value = false;
  } catch (error) {
    console.error("Failed to fetch earthquakes:", error);
    loading.value = false;
  }
}

function getChartOption(data) {
  const baseOption = {
    backgroundColor: "#020b14",
    title: {
      text: 'Global Seismic Activity',
      subtext: isHeatmapMode.value ? 'Spatial Density Analysis' : 'Real-time Event Monitoring',
      left: 'center',
      top: 20,
      textStyle: {
        color: '#fff',
        fontSize: 20,
        fontWeight: 'bold',
        fontFamily: 'Helvetica Neue'
      },
      subtextStyle: {
        color: '#aaa',
        fontSize: 12
      }
    },
    tooltip: {
      trigger: "item",
      backgroundColor: 'rgba(20, 20, 20, 0.9)',
      borderColor: '#444',
      borderWidth: 1,
      padding: 12,
      textStyle: { color: '#fff' },
      formatter: (params) => {
        if (params.seriesType === 'heatmap') return; // 热力图通常不显示单个点详情
        const d = params.data;
        if (!d) return '';
        return `
          <div style="font-family: monospace; border-bottom: 1px solid #555; padding-bottom: 5px; margin-bottom: 5px; font-weight: bold; color: #409eff;">
            ${d.region}
          </div>
          <div style="display: grid; grid-template-columns: auto auto; gap: 5px 15px; font-size: 12px;">
            <span style="color: #aaa;">Magnitude:</span>
            <span style="font-weight: bold; color:${getColorByMagnitude(d.magnitude)}">${d.magnitude.toFixed(1)}</span>
            
            <span style="color: #aaa;">Location:</span>
            <span>${formatCoordinate(d.value[0], d.value[1])}</span>
            
            <span style="color: #aaa;">Depth:</span>
            <span>${d.depth || 'N/A'} km</span>
            
            <span style="color: #aaa;">Time:</span>
            <span>${dayjs(d.time).format('HH:mm:ss')}</span>
          </div>
        `;
      },
    },
    geo: {
      map: "world",
      roam: true,
      zoom: 1.2,
      label: { show: false },
      itemStyle: {
        areaColor: "#1a2639", // 深色陆地
        borderColor: "#2c3e50", // 边境线
        borderWidth: 1,
      },
      emphasis: {
        itemStyle: {
          areaColor: "#2a3b55",
        },
        label: { show: false }
      },
    },
    visualMap: isHeatmapMode.value ? {
      min: 0,
      max: 10, // 热力图密度阈值，根据实际数据调整
      calculable: true,
      realtime: false,
      inRange: {
        color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
      },
      textStyle: { color: '#fff' },
      left: 'left',
      bottom: '20'
    } : null,
    series: []
  };

  if (isHeatmapMode.value) {
    // GIS: 热力图模式 - 展示空间分布密度
    baseOption.series.push({
      name: 'Earthquake Density',
      type: 'heatmap',
      coordinateSystem: 'geo',
      data: data.map(q => [q.longitude, q.latitude, q.magnitude * 2]), // 权重可以是震级
      pointSize: 10,
      blurSize: 15
    });
  } else {
    // 散点图模式
    baseOption.series.push({
      name: "Earthquakes",
      type: "effectScatter",
      coordinateSystem: "geo",
      data: data.map((q) => ({
        name: q.region,
        value: [q.longitude, q.latitude, q.magnitude],
        magnitude: q.magnitude,
        region: q.region,
        time: q.time,
        depth: q.depth
      })),
      // 调整光点大小：基础大小 + 指数增长，使大地震更震撼
      symbolSize: (val) => {
        const mag = val[2];
        return 6 + Math.pow(mag, 2.2) * 0.8; 
      },
      showEffectOn: 'render',
      rippleEffect: {
        brushType: 'stroke',
        scale: 3,
        period: 4 // 动画速度
      },
      itemStyle: {
        color: (params) => getColorByMagnitude(params.data.magnitude),
        shadowBlur: 15,
        shadowColor: (params) => getColorByMagnitude(params.data.magnitude) // 光晕颜色跟随震级
      },
      zlevel: 1,
    });
  }

  return baseOption;
}

function updateChart() {
  if (!chartInstance) return;
  chartInstance.clear();
  const option = getChartOption(filteredQuakes.value);
  chartInstance.setOption(option);
}

function focusOnQuake(quake) {
  if (!chartInstance) return;
  
  chartInstance.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: filteredQuakes.value.indexOf(quake)
  });

  const option = chartInstance.getOption();
  option.geo[0].center = [quake.longitude, quake.latitude];
  option.geo[0].zoom = 5; // 放大
  chartInstance.setOption(option);
}

// --- 生命周期 ---
onMounted(async () => {
  await loadWorldMap();
  chartInstance = echarts.init(chartRef.value);
  
  await fetchEarthquakes();
  updateChart();

  // 监听窗口大小
  window.addEventListener("resize", () => chartInstance && chartInstance.resize());

  // 定时刷新数据
  timerId = setInterval(async () => {
    await fetchEarthquakes();
  }, 30000);

  // 时钟
  clockId = setInterval(() => {
    currentTime.value = dayjs().format("YYYY-MM-DD HH:mm:ss");
  }, 1000);
});

onBeforeUnmount(() => {
  clearInterval(timerId);
  clearInterval(clockId);
  window.removeEventListener("resize", () => chartInstance && chartInstance.resize());
  if (chartInstance) chartInstance.dispose();
});

// 监听数据变化更新图表
watch([filteredQuakes, isHeatmapMode], () => {
  updateChart();
}, { deep: true });

</script>

<style scoped>
.layout-container {
  height: 100vh;
  background-color: #020b14;
}

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

.main-content {
  height: calc(100vh - 60px);
  overflow: hidden;
}

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

.map-container {
  padding: 0;
  position: relative;
  background-color: #020b14;
}

.map-legend {
  position: absolute;
  bottom: 20px;
  right: 20px;
  background-color: rgba(22, 36, 56, 0.9);
  border: 1px solid #2c3e50;
  padding: 15px;
  border-radius: 4px;
  color: #fff;
  font-size: 12px;
  z-index: 10;
  backdrop-filter: blur(4px);
}

.legend-title {
  font-weight: bold;
  margin-bottom: 10px;
  color: #909399;
  text-transform: uppercase;
  font-size: 11px;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.color-box {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  margin-right: 8px;
  display: inline-block;
}

.chart {
  width: 100%;
  height: 100%;
}

.loading-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0,0,0,0.7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #409eff;
  gap: 10px;
  z-index: 100;
}
</style>
