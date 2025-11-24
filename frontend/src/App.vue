<template>
  <el-container class="layout-container" direction="vertical">
    <TopHeader 
      v-model:showPlates="showPlates"
      v-model:mapStyle="mapStyle"
      v-model:isHeatmapMode="isHeatmapMode"
      :currentTime="currentTime"
    />

    <el-container class="main-content">
      <Sidebar 
        :filteredQuakes="filteredQuakes"
        v-model:minMag="minMag"
        v-model:showCluster="showCluster"
        v-model:showBuffer="showBuffer"
        v-model:enableNearestQuery="enableNearestQuery"
        @quake-selected="handleQuakeSelected"
      />

      <EarthquakeMap 
        ref="mapRef"
        :earthquakes="filteredQuakes"
        :platesData="platesData"
        :isHeatmapMode="isHeatmapMode"
        :showPlates="showPlates"
        :mapStyle="mapStyle"
        :loading="loading"
        :showCluster="showCluster"
        :showBuffer="showBuffer"
        :enableNearestQuery="enableNearestQuery"
      />
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import axios from "axios";
import dayjs from "dayjs";
import TopHeader from "./components/TopHeader.vue";
import Sidebar from "./components/Sidebar.vue";
import EarthquakeMap from "./components/EarthquakeMap.vue";

// --- 状态 ---
const mapRef = ref(null);
const earthquakes = ref([]);
const platesData = ref([]); // 板块数据
const loading = ref(true);
const currentTime = ref(dayjs().format("YYYY-MM-DD HH:mm:ss"));
const minMag = ref(2.5); // 默认过滤掉小地震
const isHeatmapMode = ref(false); // GIS: 切换可视化模式
const showPlates = ref(false); // GIS: 显示板块边界
const mapStyle = ref("dark"); // GIS: 底图风格
// GIS Advanced Features
const showCluster = ref(false);
const showBuffer = ref(false);
const enableNearestQuery = ref(false);

let timerId = null;
let clockId = null;

// --- 计算属性 ---
const filteredQuakes = computed(() => {
  return earthquakes.value
    .filter((q) => q.magnitude >= minMag.value)
    .sort((a, b) => new Date(b.time) - new Date(a.time));
});

// --- 逻辑 ---
async function loadPlatesData() {
  try {
    const res = await axios.get("/plates.json");
    platesData.value = res.data;
  } catch (error) {
    console.error("Failed to load plates data:", error);
  }
}

async function fetchEarthquakes() {
  try {
    const res = await axios.get("/earthquakes");
    earthquakes.value = res.data;
    loading.value = false;
  } catch (error) {
    console.error("Failed to fetch earthquakes:", error);
    loading.value = false;
  }
}

function handleQuakeSelected(quake) {
  if (mapRef.value) {
    mapRef.value.focusOnQuake(quake);
  }
}

// --- 生命周期 ---
onMounted(async () => {
  await Promise.all([fetchEarthquakes(), loadPlatesData()]);

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
});
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background-color: #020b14;
}

.main-content {
  height: calc(100vh - 60px);
  overflow: hidden;
}
</style>
