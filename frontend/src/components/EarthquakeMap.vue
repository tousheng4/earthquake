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
  </el-main>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import * as echarts from "echarts";
import axios from "axios";
import dayjs from "dayjs";
import { getColorByMagnitude, formatCoordinate } from '../utils/formatters';

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
  loading: Boolean
});

const chartRef = ref(null);
let chartInstance = null;

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
        if (params.seriesType === "lines") return `<div>Plate Boundary: ${params.data.name}</div>`;
        
        const d = params.data;
        if (!d) return "";
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

  // 2. 地震数据图层
  if (props.isHeatmapMode) {
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

function updateChart() {
  if (!chartInstance) return;
  chartInstance.clear();
  const option = getChartOption(props.earthquakes);
  chartInstance.setOption(option);
}

function focusOnQuake(quake) {
  if (!chartInstance) return;
  
  chartInstance.dispatchAction({
    type: "showTip",
    seriesIndex: 0,
    dataIndex: props.earthquakes.indexOf(quake)
  });

  const option = chartInstance.getOption();
  option.geo[0].center = [quake.longitude, quake.latitude];
  option.geo[0].zoom = 5; // 放大
  chartInstance.setOption(option);
}

defineExpose({ focusOnQuake });

onMounted(async () => {
  await loadWorldMap();
  chartInstance = echarts.init(chartRef.value);
  updateChart();
  window.addEventListener("resize", () => chartInstance && chartInstance.resize());
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", () => chartInstance && chartInstance.resize());
  if (chartInstance) chartInstance.dispose();
});

watch(() => [props.earthquakes, props.isHeatmapMode, props.showPlates, props.mapStyle], () => {
  updateChart();
}, { deep: true });

</script>

<style scoped>
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
