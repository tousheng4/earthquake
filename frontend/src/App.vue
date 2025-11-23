<template>
  <div class="app">
    <h1 class="title">Real-Time Earthquake Map</h1>
    <div ref="chartRef" class="chart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import * as echarts from "echarts";
import axios from "axios";

// 图表 DOM 引用
const chartRef = ref(null);
// ECharts 实例
let chartInstance = null;
// 定时器 ID
let timerId = null;

// 后端 API 基地址
const BACKEND_BASE_URL = "http://127.0.0.1:5000";

// 按震级返回颜色
function getColorByMagnitude(mag) {
  if (mag < 2.5) return "#2ecc71"; // 绿
  if (mag < 4.0) return "#f1c40f"; // 黄
  if (mag < 5.5) return "#e67e22"; // 橙
  return "#e74c3c";               // 红
}

// 加载世界地图 GeoJSON 并注册到 ECharts
async function loadWorldMap() {
  const res = await axios.get("/world.json"); // 从 public 目录取
  echarts.registerMap("world", res.data);
}

// 从后端获取地震数据
async function fetchEarthquakes() {
  const res = await axios.get(`${BACKEND_BASE_URL}/earthquakes`);
  return res.data;
}

// 根据数据渲染 / 更新图表
async function renderChart() {
  const quakes = await fetchEarthquakes();

  // 转成 ECharts scatter 需要的数据格式
  const data = quakes.map((q) => ({
    name: q.region,
    value: [q.longitude, q.latitude, q.magnitude], // [lon, lat, mag]
    magnitude: q.magnitude,
    region: q.region,
    time: q.time,
  }));

  const option = {
    backgroundColor: "#ffffff",
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        const d = params.data;
        return `
          <div>
            <strong>Magnitude:</strong> ${d.magnitude.toFixed(1)}<br/>
            <strong>Region:</strong> ${d.region}<br/>
            <strong>Time:</strong> ${d.time}
          </div>
        `;
      },
    },
    geo: {
      map: "world",
      roam: true, // 允许缩放和平移
      itemStyle: {
        areaColor: "#f2f2f2",
        borderColor: "#999",
      },
      emphasis: {
        itemStyle: {
          areaColor: "#e0e0e0",
        },
      },
    },
    series: [
      {
        name: "Earthquakes",
        type: "scatter",
        coordinateSystem: "geo",
        data,
        symbolSize: (val) => {
          // val[2] 是 magnitude
          return 4 * val[2]; // 放大系数可以按需调整
        },
        itemStyle: {
          color: (params) => getColorByMagnitude(params.data.magnitude),
          opacity: 0.8,
        },
        label: {
          show: true,
          formatter: (params) => params.data.magnitude.toFixed(1),
          position: "inside",
          color: "#000",
          fontSize: 9,
        },
      },
    ],
  };

  chartInstance.setOption(option);
}

// 初始化图表：加载地图 → 创建实例 → 首次渲染 → 启动定时刷新
async function initChart() {
  await loadWorldMap();

  chartInstance = echarts.init(chartRef.value);

  await renderChart(); // 先渲染一次

  // 每 30 秒刷新一次数据
  timerId = window.setInterval(() => {
    renderChart().catch((err) => console.error(err));
  }, 30000);
}

// 组件挂载时初始化图表
onMounted(() => {
  initChart().catch((err) => console.error(err));
  // 自适应窗口大小
  window.addEventListener("resize", handleResize);
});

// 组件卸载时清理
onBeforeUnmount(() => {
  if (timerId) {
    window.clearInterval(timerId);
  }
  window.removeEventListener("resize", handleResize);
  if (chartInstance) {
    chartInstance.dispose();
  }
});

// 窗口变化时，让图表自适应大小
function handleResize() {
  if (chartInstance) {
    chartInstance.resize();
  }
}
</script>

<style scoped>
.app {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.title {
  text-align: center;
  font-size: 20px;
  margin: 8px 0;
}

.chart {
  flex: 1;
  /* 留一点边距 */
  margin: 0 8px 8px 8px;
}
</style>
