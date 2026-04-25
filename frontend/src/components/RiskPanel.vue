<template>
  <el-card shadow="hover" class="risk-card">
    <template #header>
      <div class="risk-header">
        <div>
          <div class="risk-title">Risk Ranking</div>
          <div class="risk-subtitle">Priority events from the backend risk service</div>
        </div>
        <el-button size="small" type="primary" plain :loading="loading" @click="fetchRanking">
          Refresh
        </el-button>
      </div>
    </template>

    <div class="risk-controls">
      <el-select v-model="hours" size="small" class="control-select">
        <el-option label="Recent 30 Days" :value="24 * 30" />
        <el-option label="Recent 90 Days" :value="24 * 90" />
        <el-option label="Recent 3 Years" :value="30000" />
      </el-select>
      <el-select v-model="minRiskLevel" size="small" class="control-select">
        <el-option label="All Levels" value="low" />
        <el-option label="Medium and Above" value="medium" />
        <el-option label="High Only" value="high" />
      </el-select>
    </div>

    <el-alert
      v-if="errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="risk-alert"
      :title="errorMessage"
    />

    <div v-loading="loading" class="risk-list-wrapper">
      <el-empty v-if="!loading && ranking.length === 0" description="No risk results yet" :image-size="56" />

      <el-scrollbar v-else>
        <ul class="risk-list">
          <li
            v-for="item in ranking"
            :key="item.event_unid"
            class="risk-item"
            @click="openDetail(item.event_unid)"
          >
            <div class="risk-item-top">
              <div class="risk-score-block">
                <span class="risk-score">{{ Number(item.risk_score || 0).toFixed(1) }}</span>
                <span class="risk-score-label">score</span>
              </div>
              <el-tag
                size="small"
                effect="dark"
                :type="riskTagType(item.risk_level)"
              >
                {{ displayRiskLevel(item.risk_level) }}
              </el-tag>
            </div>

            <div class="risk-region">{{ item.region || "UNKNOWN" }}</div>

            <div class="risk-meta">
              <span>Mag {{ formatMagnitude(item.magnitude) }}</span>
              <span>{{ formatTime(item.event_time) }}</span>
            </div>
          </li>
        </ul>
      </el-scrollbar>
    </div>
  </el-card>

  <el-drawer
    v-model="detailVisible"
    title="Risk Assessment Detail"
    size="420px"
    :destroy-on-close="false"
  >
    <div v-loading="detailLoading" class="detail-content">
      <el-empty
        v-if="!detailLoading && !detailData"
        description="No detail available"
        :image-size="56"
      />

      <template v-else-if="detailData">
        <el-descriptions :column="1" border size="small" class="detail-block">
          <el-descriptions-item label="Region">{{ detailData.event.region || "UNKNOWN" }}</el-descriptions-item>
          <el-descriptions-item label="Time">{{ formatDetailTime(detailData.event.event_time) }}</el-descriptions-item>
          <el-descriptions-item label="Magnitude">M {{ formatMagnitude(detailData.event.magnitude) }}</el-descriptions-item>
          <el-descriptions-item label="Depth">{{ formatDepth(detailData.event.depth) }}</el-descriptions-item>
          <el-descriptions-item label="Risk Level">{{ displayRiskLevel(detailData.risk.risk_level) }}</el-descriptions-item>
          <el-descriptions-item label="Risk Score">{{ Number(detailData.risk.risk_score || 0).toFixed(1) }}</el-descriptions-item>
        </el-descriptions>

        <el-card shadow="never" class="detail-block detail-summary">
          <template #header>
            <div class="detail-section-title">Assessment Summary</div>
          </template>
          <p class="detail-text">{{ detailData.risk.explanation || "No explanation available." }}</p>
        </el-card>

        <el-card shadow="never" class="detail-block">
          <template #header>
            <div class="detail-section-title">Feature Snapshot</div>
          </template>
          <div class="feature-grid">
            <div class="feature-item">
              <span class="feature-label">Recent Count</span>
              <span class="feature-value">{{ safeValue(detailData.feature_summary.recent_region_event_count) }}</span>
            </div>
            <div class="feature-item">
              <span class="feature-label">Recent Avg Mag</span>
              <span class="feature-value">{{ safeDecimal(detailData.feature_summary.recent_region_avg_magnitude) }}</span>
            </div>
            <div class="feature-item">
              <span class="feature-label">Baseline Years</span>
              <span class="feature-value">{{ safeValue(detailData.feature_summary.historical_baseline_years) }}</span>
            </div>
            <div class="feature-item">
              <span class="feature-label">Anomaly Score</span>
              <span class="feature-value">{{ safeDecimal(detailData.feature_summary.anomaly_score) }}</span>
            </div>
          </div>
        </el-card>
      </template>
    </div>
  </el-drawer>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import axios from "axios";
import dayjs from "dayjs";
import { formatTime } from "../utils/formatters";

const ranking = ref([]);
const loading = ref(false);
const detailLoading = ref(false);
const errorMessage = ref("");
const detailVisible = ref(false);
const detailData = ref(null);
const hours = ref(30000);
const minRiskLevel = ref("low");

function displayRiskLevel(level) {
  const value = String(level || "low").toLowerCase();
  if (value === "high") return "HIGH";
  if (value === "medium") return "MEDIUM";
  return "LOW";
}

function riskTagType(level) {
  const value = String(level || "low").toLowerCase();
  if (value === "high") return "danger";
  if (value === "medium") return "warning";
  return "info";
}

function formatMagnitude(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : "--";
}

function formatDepth(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)} km` : "--";
}

function formatDetailTime(value) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "--";
}

function safeValue(value) {
  return value ?? "--";
}

function safeDecimal(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : "--";
}

async function fetchRanking() {
  loading.value = true;
  errorMessage.value = "";

  try {
    const res = await axios.get("/risk/ranking", {
      params: {
        hours: hours.value,
        limit: 5,
        min_risk_level: minRiskLevel.value,
      },
    });
    ranking.value = Array.isArray(res.data) ? res.data : [];
  } catch (error) {
    console.error("Failed to fetch risk ranking:", error);
    ranking.value = [];
    errorMessage.value = "Failed to load risk ranking.";
  } finally {
    loading.value = false;
  }
}

async function openDetail(eventUnid) {
  detailVisible.value = true;
  detailLoading.value = true;
  detailData.value = null;

  try {
    const res = await axios.get(`/risk/events/${eventUnid}`);
    detailData.value = res.data || null;
  } catch (error) {
    console.error("Failed to fetch risk detail:", error);
    detailData.value = null;
  } finally {
    detailLoading.value = false;
  }
}

watch([hours, minRiskLevel], fetchRanking);

onMounted(fetchRanking);
</script>

<style scoped>
.risk-card {
  background-color: #162438;
  border: 1px solid #2c3e50;
  color: #fff;
}

.risk-card :deep(.el-card__header) {
  padding: 12px 14px;
  border-bottom: 1px solid #2c3e50;
}

.risk-card :deep(.el-card__body) {
  padding: 14px;
}

.risk-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-title {
  font-size: 14px;
  font-weight: 700;
}

.risk-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #8aa0b8;
}

.risk-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}

.control-select {
  width: 100%;
}

.risk-alert {
  margin-bottom: 12px;
}

.risk-list-wrapper {
  min-height: 220px;
  max-height: 320px;
}

.risk-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.risk-item {
  padding: 12px;
  border: 1px solid #25384d;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(31, 45, 61, 0.95), rgba(22, 36, 56, 0.95));
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.risk-item:hover {
  border-color: #409eff;
  transform: translateY(-1px);
}

.risk-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.risk-score-block {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.risk-score {
  font-size: 20px;
  font-weight: 700;
  color: #ffd166;
}

.risk-score-label {
  font-size: 12px;
  color: #8aa0b8;
  text-transform: uppercase;
}

.risk-region {
  margin-top: 10px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  color: #f3f7fb;
}

.risk-meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: #8aa0b8;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-block {
  border: 1px solid #e4e7ed;
}

.detail-section-title {
  font-weight: 700;
}

.detail-summary :deep(.el-card__body) {
  padding-top: 10px;
}

.detail-text {
  margin: 0;
  line-height: 1.7;
  color: #334155;
}

.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.feature-item {
  padding: 10px;
  border-radius: 8px;
  background-color: #f5f7fa;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.feature-label {
  font-size: 12px;
  color: #64748b;
}

.feature-value {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

@media (max-width: 1200px) {
  .risk-controls {
    grid-template-columns: 1fr;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }
}
</style>
