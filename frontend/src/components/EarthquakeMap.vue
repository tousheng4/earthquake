<template>
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

    <div class="nearest-result" v-if="nearestResult">
      <div class="nearest-label">Nearest Epicenter</div>
      <div class="nearest-region">{{ nearestResult.region || "UNKNOWN" }}</div>
      <div class="nearest-distance">{{ nearestResult.distanceKm }} km away</div>
    </div>

    <div class="selected-quake-card" v-if="selectedQuake">
      <div class="selected-label">Selected Earthquake</div>
      <div class="selected-region">{{ selectedQuake.region || "UNKNOWN" }}</div>
      <div class="selected-grid">
        <div>
          <span>Magnitude</span>
          <strong>M {{ formatMagnitude(selectedQuake.magnitude) }}</strong>
        </div>
        <div>
          <span>Depth</span>
          <strong>{{ formatDepth(selectedQuake.depth) }}</strong>
        </div>
        <div class="selected-time">
          <span>Time</span>
          <strong>{{ formatSelectedTime(selectedQuake.time) }}</strong>
        </div>
      </div>
    </div>

    <!-- 时间轴控件 -->
    <div class="time-slider-container" v-if="earthquakes.length > 0">
      <div class="control-row">
        <el-button 
          circle 
          :icon="isPlaying ? VideoPause : VideoPlay" 
          @click="togglePlay"
          class="play-btn"
          type="primary"
        />
        <div class="slider-wrapper">
          <span class="time-label">{{ formatTimeLabel(minTime) }}</span>
          <el-slider 
            v-model="sliderValue" 
            :min="minTime" 
            :max="maxTime" 
            :format-tooltip="formatTooltip"
            class="custom-slider"
            :show-tooltip="false"
          />
          <span class="time-label">{{ formatTimeLabel(maxTime) }}</span>
        </div>
      </div>
      <div class="current-time-display">
        Current: {{ sliderLabel }}
      </div>
    </div>
  </el-main>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from "vue";
import * as echarts from "echarts";
import axios from "axios";
import dayjs from "dayjs";
import { getColorByMagnitude, formatCoordinate } from '../utils/formatters';
import { VideoPlay, VideoPause } from '@element-plus/icons-vue';

const props = defineProps({
  earthquakes: {
    type: Array,
    default: () => []
  },
  platesData: {
    type: Array,
    default: () => []
  },
  isHeatmapMode: Boolean,
  showPlates: Boolean,
  mapStyle: String,
  loading: Boolean,
  // GIS Features
  showBuffer: Boolean,
  enableNearestQuery: Boolean,
  showCluster: Boolean
});

const chartRef = ref(null);
let chartInstance = null;

// --- GIS State ---
const bufferData = ref(null); // GeoJSON for buffer
const clusterData = ref([]); // Data for cluster view
const nearestLine = ref(null); // Line to nearest quake
const nearestResult = ref(null);
const nearestPoints = ref([]);
const selectedQuake = ref(null);

// --- Playback State ---
const isPlaying = ref(false);
const sliderValue = ref(0); // Current timestamp
const minTime = ref(0);
const maxTime = ref(0);
let playbackTimer = null;

// --- Computed ---
const displayedQuakes = computed(() => {
  if (!props.earthquakes.length) return [];
  // Show earthquakes that happened <= sliderValue
  return props.earthquakes.filter(q => new Date(q.time).getTime() <= sliderValue.value);
});

const sliderLabel = computed(() => {
  return dayjs(sliderValue.value).format("YYYY-MM-DD HH:mm:ss");
});

function formatTimeLabel(ts) {
  return dayjs(ts).format('MM-DD HH:mm');
}

// --- Watchers ---
watch(() => props.earthquakes, (newVal) => {
  if (newVal.length > 0) {
    const times = newVal.map(q => new Date(q.time).getTime());
    minTime.value = Math.min(...times);
    maxTime.value = Math.max(...times);
    
    // If not playing and slider is at the end (or uninitialized), snap to end
    if (!isPlaying.value && (sliderValue.value === 0 || sliderValue.value >= maxTime.value)) {
      sliderValue.value = maxTime.value;
    }
  }
}, { immediate: true });

watch(displayedQuakes, (newVal) => {
  if (chartInstance) {
    const option = getChartOption(newVal);
    chartInstance.setOption(option);
  }
});

// --- Playback Logic ---
function togglePlay() {
  isPlaying.value = !isPlaying.value;
  if (isPlaying.value) {
    if (sliderValue.value >= maxTime.value) {
      sliderValue.value = minTime.value;
    }
    startPlayback();
  } else {
    stopPlayback();
  }
}

function startPlayback() {
  stopPlayback();
  // Duration of playback in ms (e.g., 10 seconds for the whole range)
  const playbackDuration = 15000; // Slower playback
  const interval = 50; // Update every 50ms
  const totalSteps = playbackDuration / interval;
  const timeRange = maxTime.value - minTime.value;
  const stepSize = timeRange / totalSteps;

  playbackTimer = setInterval(() => {
    if (sliderValue.value + stepSize >= maxTime.value) {
      sliderValue.value = maxTime.value;
      isPlaying.value = false;
      stopPlayback();
    } else {
      sliderValue.value += stepSize;
    }
  }, interval);
}

function stopPlayback() {
  if (playbackTimer) {
    clearInterval(playbackTimer);
    playbackTimer = null;
  }
}

function formatTooltip(val) {
  return dayjs(val).format("YYYY-MM-DD HH:mm");
}

function formatMagnitude(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : "--";
}

function formatDepth(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)} km` : "--";
}

function formatSelectedTime(value) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "--";
}

function geometryToRings(geometry) {
  if (!geometry) return [];
  if (geometry.type === "Polygon") {
    return geometry.coordinates || [];
  }
  if (geometry.type === "MultiPolygon") {
    return (geometry.coordinates || []).flat();
  }
  return [];
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

function getMapStyleConfig(style) {
  switch (style) {
    case "light":
      return {
        bgColor: "#f0f2f5",
        areaColor: "#e0e0e0",
        borderColor: "#999",
        textColor: "#333",
        emphasisColor: "#ccc"
      };
    case "terrain":
      return {
        bgColor: "#a3ccff", // 海洋蓝
        areaColor: "#e0d0b0", // 陆地黄
        borderColor: "#a09070",
        textColor: "#333",
        emphasisColor: "#d0c0a0"
      };
    case "dark":
    default:
      return {
        bgColor: "#020b14",
        areaColor: "#1a2639",
        borderColor: "#2c3e50",
        textColor: "#fff",
        emphasisColor: "#2a3b55"
      };
  }
}

function getChartOption(data) {
  const styleConfig = getMapStyleConfig(props.mapStyle);

  const baseOption = {
    backgroundColor: styleConfig.bgColor,
    title: {
      text: "Global Seismic Activity",
      subtext: props.isHeatmapMode ? "Spatial Density Analysis" : "Real-time Event Monitoring",
      left: "center",
      top: 20,
      textStyle: {
        color: styleConfig.textColor,
        fontSize: 20,
        fontWeight: "bold",
        fontFamily: "Helvetica Neue"
      },
      subtextStyle: {
        color: styleConfig.textColor === "#fff" ? "#aaa" : "#666",
        fontSize: 12
      }
    },
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(20, 20, 20, 0.9)",
      borderColor: "#444",
      borderWidth: 1,
      padding: 12,
      textStyle: { color: "#fff" },
      formatter: (params) => {
        if (params.seriesType === "heatmap") return;
        if (params.seriesType === "lines" && params.seriesName === "Tectonic Plates") return `<div>Plate Boundary: ${params.data.name}</div>`;
        if (params.seriesType === "lines" && params.seriesName === "Nearest Link") return `<div>Distance: ${(params.data.distance / 1000).toFixed(1)} km</div>`;
        
        const d = params.data;
        if (!d) return "";
        
        // Cluster Tooltip
        if (props.showCluster && d.count) {
           return `
            <div style="font-weight: bold; color: #e6a23c;">Cluster Info</div>
            <div>Count: ${d.count}</div>
            <div>Avg Mag: ${d.avg_magnitude.toFixed(1)}</div>
           `;
        }

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
            <span>${d.depth || "N/A"} km</span>
            
            <span style="color: #aaa;">Time:</span>
            <span>${dayjs(d.time).format("HH:mm:ss")}</span>
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
        areaColor: styleConfig.areaColor,
        borderColor: styleConfig.borderColor,
        borderWidth: 1,
      },
      emphasis: {
        itemStyle: {
          areaColor: styleConfig.emphasisColor,
        },
        label: { show: false }
      },
    },
    visualMap: props.isHeatmapMode ? {
      min: 0,
      max: 10,
      calculable: true,
      realtime: false,
      inRange: {
        color: ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#ffffbf", "#fee090", "#fdae61", "#f46d43", "#d73027", "#a50026"]
      },
      textStyle: { color: styleConfig.textColor },
      left: "left",
      bottom: "20"
    } : null,
    series: []
  };

  // 1. 板块边界图层
  if (props.showPlates && props.platesData.length > 0) {
    baseOption.series.push({
      type: "lines",
      name: "Tectonic Plates",
      coordinateSystem: "geo",
      polyline: true,
      data: props.platesData,
      lineStyle: {
        color: "#ff00ff", // 醒目的洋红色
        width: 2,
        opacity: 0.7,
        type: "dashed"
      },
      zlevel: 2
    });
  }

  // 2. 缓冲区图层 (GIS)
  if (props.showBuffer && bufferData.value?.features?.length) {
    baseOption.series.push({
      type: "custom",
      name: "Earthquake Buffers",
      coordinateSystem: "geo",
      data: bufferData.value.features,
      renderItem: (params, api) => {
        const feature = bufferData.value.features[params.dataIndex];
        const rings = geometryToRings(feature?.geometry);
        if (!rings.length) return null;

        return {
          type: "group",
          children: rings.map((ring) => ({
            type: "polygon",
            shape: {
              points: ring.map((coord) => api.coord(coord))
            },
            style: {
              fill: "rgba(255, 64, 64, 0.12)",
              stroke: "#ff4040",
              lineWidth: 1,
              lineDash: [6, 4]
            },
            silent: true
          }))
        };
      },
      zlevel: 2,
      silent: true
    });
  }

  // 3. 最近邻连线 (GIS)
  if (nearestLine.value) {
    baseOption.series.push({
      type: "lines",
      name: "Nearest Link",
      coordinateSystem: "geo",
      data: [nearestLine.value],
      lineStyle: {
        color: "#00ff00",
        width: 2,
        curveness: 0.2
      },
      effect: {
        show: true,
        period: 6,
        trailLength: 0.7,
        color: '#fff',
        symbolSize: 3
      },
      zlevel: 3
    });

    baseOption.series.push({
      type: "scatter",
      name: "Nearest Query Points",
      coordinateSystem: "geo",
      data: nearestPoints.value,
      symbolSize: (value, params) => params.data.role === "clicked" ? 13 : 16,
      itemStyle: {
        color: (params) => params.data.role === "clicked" ? "#ffffff" : "#1ecf77",
        borderColor: "#0d1b2a",
        borderWidth: 2
      },
      label: {
        show: true,
        formatter: (params) => params.data.role === "clicked" ? "Clicked" : "Nearest",
        position: "right",
        color: "#fff",
        fontSize: 12,
        fontWeight: 700
      },
      zlevel: 4
    });
  }

  // 4. 数据图层 (Cluster or Normal)
  if (props.showCluster) {
    // Cluster View
    const clusters = Array.isArray(clusterData.value) ? clusterData.value : [];
    baseOption.series.push({
      name: "Earthquake Clusters",
      type: "scatter",
      coordinateSystem: "geo",
      data: clusters.map(c => ({
        value: [c.center_lon, c.center_lat, c.count],
        count: c.count,
        avg_magnitude: c.avg_magnitude
      })),
      symbolSize: (val) => {
        // Scale symbol size by count
        return Math.min(10 + Math.sqrt(val[2]) * 5, 60);
      },
      itemStyle: {
        color: (params) => {
           // Color by avg magnitude
           return getColorByMagnitude(params.data.avg_magnitude);
        },
        shadowBlur: 10,
        shadowColor: '#333'
      },
      label: {
        show: true,
        formatter: '{@[2]}',
        fontSize: 16,
        fontWeight: 700,
        color: '#fff'
      },
      zlevel: 1
    });

  } else if (props.isHeatmapMode) {
    baseOption.series.push({
      name: "Earthquake Density",
      type: "heatmap",
      coordinateSystem: "geo",
      data: data.map(q => [q.longitude, q.latitude, q.magnitude * 2]),
      pointSize: 10,
      blurSize: 15,
      zlevel: 1
    });
  } else {
    // Normal Scatter
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
      symbolSize: (val) => {
        const mag = val[2];
        return 6 + Math.pow(mag, 2.2) * 0.8; 
      },
      showEffectOn: "render",
      rippleEffect: {
        brushType: "stroke",
        scale: 3,
        period: 4
      },
      itemStyle: {
        color: (params) => getColorByMagnitude(params.data.magnitude),
        shadowBlur: 15,
        shadowColor: (params) => getColorByMagnitude(params.data.magnitude)
      },
      zlevel: 1,
    });
  }

  return baseOption;
}

// --- GIS Actions ---
async function fetchBuffer(quake) {
  if (!props.showBuffer) return;
  if (!quake?.unid) return;
  try {
    bufferData.value = null;
    updateChart();
    const res = await axios.get(
      `/earthquakes/buffer?radius_km=200&hours=48&unid=${encodeURIComponent(quake.unid)}`,
    );
    bufferData.value = res.data;
    updateChart();
  } catch (e) {
    console.error("Buffer fetch failed", e);
  }
}

async function fetchCluster() {
  try {
    const res = await axios.get(`/stats/cluster?cell_km=100&hours=48`);
    if (Array.isArray(res.data)) {
      clusterData.value = res.data;
      updateChart();
    } else {
      console.error("Cluster data is not an array:", res.data);
      clusterData.value = [];
    }
  } catch (e) {
    console.error("Cluster fetch failed", e);
    clusterData.value = [];
  }
}

async function handleMapClick(params) {
  if (props.enableNearestQuery && params.componentType === 'geo') {
    // Clicked on empty map space (geo component)
    const [lon, lat] = params.coord || chartInstance.convertFromPixel('geo', [params.event.offsetX, params.event.offsetY]);
    
    try {
      const res = await axios.get(`/earthquakes/nearest?lon=${lon}&lat=${lat}&limit=1&hours=48`);
      if (res.data && res.data.length > 0) {
        const nearest = res.data[0];
        // Draw line
        nearestLine.value = {
          coords: [[lon, lat], [nearest.longitude, nearest.latitude]],
          distance: nearest.distance_m
        };
        nearestPoints.value = [
          {
            name: "Clicked Location",
            role: "clicked",
            value: [lon, lat]
          },
          {
            name: nearest.region || "Nearest Epicenter",
            role: "nearest",
            value: [nearest.longitude, nearest.latitude]
          }
        ];
        nearestResult.value = {
          region: nearest.region,
          distanceKm: (Number(nearest.distance_m || 0) / 1000).toFixed(1)
        };
        updateChart();
      }
    } catch (e) {
      console.error("Nearest fetch failed", e);
    }
  } else {
    // Clear line if clicking elsewhere
    nearestLine.value = null;
    nearestResult.value = null;
    nearestPoints.value = [];
    updateChart();
  }
}

// --- Lifecycle ---
function updateChart({ preserveView = true } = {}) {
  if (!chartInstance) return;
  const currentOption = chartInstance.getOption();
  const currentGeo = currentOption?.geo?.[0];
  chartInstance.clear();
  // Use displayedQuakes instead of props.earthquakes
  // If showing cluster, we don't use displayedQuakes for the main series
  const dataToUse = props.showCluster ? [] : displayedQuakes.value;
  const option = getChartOption(dataToUse);
  if (preserveView && currentGeo && option.geo) {
    option.geo.center = currentGeo.center;
    option.geo.zoom = currentGeo.zoom;
  }
  chartInstance.setOption(option);
}

function focusOnQuake(quake) {
  if (!chartInstance) return;
  selectedQuake.value = quake;
  
  // Ensure the quake is visible in the current time window
  if (new Date(quake.time).getTime() > sliderValue.value) {
      sliderValue.value = new Date(quake.time).getTime();
  }

  requestAnimationFrame(() => {
    const option = chartInstance.getOption();
    option.geo[0].center = [quake.longitude, quake.latitude];
    option.geo[0].zoom = 5; // 放大
    chartInstance.setOption(option);
  });

  if (props.showBuffer) {
      fetchBuffer(quake);
  }

  requestAnimationFrame(() => {
    const dataIndex = displayedQuakes.value.findIndex((item) => item.unid === quake.unid);
    if (dataIndex >= 0) {
      chartInstance.dispatchAction({
        type: "showTip",
        seriesIndex: 0,
        dataIndex
      });
    }
  });
}

defineExpose({ focusOnQuake });

onMounted(async () => {
  await loadWorldMap();
  chartInstance = echarts.init(chartRef.value);
  
  // Click event for Nearest Query
  chartInstance.getZr().on('click', (params) => {
      if (!props.enableNearestQuery) return;
      // Convert pixel to coord
      const pointInPixel = [params.offsetX, params.offsetY];
      if (chartInstance.containPixel('geo', pointInPixel)) {
          const coord = chartInstance.convertFromPixel('geo', pointInPixel);
          handleMapClick({ componentType: 'geo', coord: coord });
      }
  });

  updateChart();
  window.addEventListener("resize", () => chartInstance && chartInstance.resize());
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", () => chartInstance && chartInstance.resize());
  if (chartInstance) chartInstance.dispose();
  stopPlayback();
});

watch(() => [props.earthquakes, props.isHeatmapMode, props.showPlates, props.mapStyle, props.showBuffer, props.showCluster, props.enableNearestQuery], () => {
  if (!props.enableNearestQuery) {
      nearestLine.value = null;
      nearestResult.value = null;
      nearestPoints.value = [];
  }
  if (props.showBuffer && selectedQuake.value && !bufferData.value) {
      fetchBuffer(selectedQuake.value);
  }
  if (!props.showBuffer) {
      bufferData.value = null;
  }
  if (props.showCluster) {
      fetchCluster();
  } else {
      updateChart();
  }
}, { deep: true });

</script>

<style scoped>
.map-container {
  padding: 0;
  position: relative;
  background-color: #020b14;
  height: 100%; /* 强制占满父容器高度 */
  width: 100%;
  overflow: hidden; /* 防止内容溢出 */
  display: flex;    /* 确保内部元素布局正确 */
  flex-direction: column;
}

.map-legend {
  position: absolute;
  bottom: 90px; /* 稍微调高一点，避免被时间轴遮挡 */
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
  position: absolute; /* 绝对定位以确保占满整个容器 */
  top: 0;
  left: 0;
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

.nearest-result {
  position: absolute;
  top: 86px;
  left: 24px;
  z-index: 20;
  max-width: 280px;
  padding: 14px 16px;
  border: 1px solid #1ecf77;
  border-radius: 8px;
  background-color: rgba(13, 27, 42, 0.92);
  color: #fff;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(6px);
}

.nearest-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #1ecf77;
}

.nearest-region {
  margin-top: 6px;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
}

.nearest-distance {
  margin-top: 6px;
  font-size: 18px;
  font-weight: 800;
  color: #a7f3c4;
}

.selected-quake-card {
  position: absolute;
  top: 86px;
  right: 24px;
  z-index: 20;
  width: 320px;
  padding: 14px 16px;
  border: 1px solid #409eff;
  border-radius: 8px;
  background-color: rgba(13, 27, 42, 0.94);
  color: #fff;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(6px);
}

.selected-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #8ec5ff;
}

.selected-region {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.35;
}

.selected-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 12px;
}

.selected-grid div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border-radius: 6px;
  background-color: rgba(255, 255, 255, 0.06);
}

.selected-grid span {
  font-size: 11px;
  color: #8aa0b8;
  text-transform: uppercase;
}

.selected-grid strong {
  font-size: 14px;
  color: #fff;
}

.selected-grid .selected-time {
  grid-column: 1 / -1;
}

.time-slider-container {
  position: absolute;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  width: 70%;
  min-width: 500px;
  background-color: rgba(22, 36, 56, 0.95);
  border: 1px solid #409eff;
  padding: 15px 25px;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 20;
  backdrop-filter: blur(8px);
  color: #fff;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
}

.control-row {
  display: flex;
  align-items: center;
  gap: 15px;
  width: 100%;
}

.slider-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 15px;
}

.custom-slider {
  flex: 1;
}

.time-label {
  font-size: 12px;
  color: #a0cfff;
  font-family: monospace;
  white-space: nowrap;
}

.current-time-display {
  text-align: center;
  font-size: 14px;
  color: #409eff;
  font-weight: bold;
  font-family: monospace;
  background: rgba(0, 0, 0, 0.3);
  padding: 4px 12px;
  border-radius: 4px;
  align-self: center;
}

.play-btn {
  background-color: #409eff;
  border-color: #409eff;
  color: #fff;
}
.play-btn:hover {
  background-color: #66b1ff;
  border-color: #66b1ff;
}
</style>

