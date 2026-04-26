<template>
  <el-card shadow="hover" class="risk-card">
    <template #header>
      <div class="risk-header">
        <div>
          <div class="risk-title">Risk Ranking</div>
          <div class="risk-subtitle">
            Priority events from the backend risk service
          </div>
        </div>
        <el-button
          size="small"
          type="primary"
          plain
          :loading="loading"
          @click="fetchRanking"
        >
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
      <el-empty
        v-if="!loading && ranking.length === 0"
        description="No risk results yet"
        :image-size="56"
      />

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
                <span class="risk-score">{{
                  Number(item.risk_score || 0).toFixed(1)
                }}</span>
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

  <Teleport to="body">
    <Transition name="risk-detail-fade">
      <div
        v-if="detailVisible"
        class="risk-detail-overlay"
        @click.self="closeDetail"
      >
        <div class="risk-detail-panel" v-loading="detailLoading">
          <div class="risk-detail-header">
            <div>
              <div class="risk-detail-title">Risk Assessment Detail</div>
              <div class="risk-detail-subtitle">
                Focused event snapshot and explanation
              </div>
            </div>
            <el-button
              circle
              plain
              size="small"
              class="detail-close-btn"
              @click="closeDetail"
            >
              ×
            </el-button>
          </div>

          <div class="detail-content">
            <el-empty
              v-if="!detailLoading && !detailData"
              description="No detail available"
              :image-size="56"
            />

            <template v-else-if="detailData">
              <div class="detail-hero">
                <div class="detail-hero-copy">
                  <div class="detail-hero-kicker">Priority Assessment</div>
                  <div class="detail-hero-region">
                    {{ detailData.event.region || "UNKNOWN" }}
                  </div>
                  <div class="detail-hero-time">
                    {{ formatDetailTime(detailData.event.event_time) }}
                  </div>
                </div>
                <div class="detail-hero-metrics">
                  <div class="hero-metric">
                    <span class="hero-metric-label">Risk Level</span>
                    <span class="hero-metric-value">{{
                      displayRiskLevel(detailData.risk.risk_level)
                    }}</span>
                  </div>
                  <div class="hero-metric hero-metric-score">
                    <span class="hero-metric-label">Risk Score</span>
                    <span class="hero-metric-value">{{
                      Number(detailData.risk.risk_score || 0).toFixed(1)
                    }}</span>
                  </div>
                </div>
              </div>

              <div class="detail-top-grid">
                <el-card shadow="never" class="detail-block">
                  <template #header>
                    <div class="detail-section-title">Event Snapshot</div>
                  </template>
                  <div class="event-facts">
                    <div class="event-fact">
                      <span class="event-fact-label">Region</span>
                      <span class="event-fact-value">{{
                        detailData.event.region || "UNKNOWN"
                      }}</span>
                    </div>
                    <div class="event-fact">
                      <span class="event-fact-label">Time</span>
                      <span class="event-fact-value">{{
                        formatDetailTime(detailData.event.event_time)
                      }}</span>
                    </div>
                    <div class="event-fact">
                      <span class="event-fact-label">Magnitude</span>
                      <span class="event-fact-value"
                        >M
                        {{ formatMagnitude(detailData.event.magnitude) }}</span
                      >
                    </div>
                    <div class="event-fact">
                      <span class="event-fact-label">Depth</span>
                      <span class="event-fact-value">{{
                        formatDepth(detailData.event.depth)
                      }}</span>
                    </div>
                  </div>
                </el-card>

                <el-card shadow="never" class="detail-block">
                  <template #header>
                    <div class="detail-section-title">Feature Snapshot</div>
                  </template>
                  <div class="feature-grid">
                    <div class="feature-item">
                      <span class="feature-label">Recent Count</span>
                      <span class="feature-value">{{
                        safeValue(
                          detailData.feature_summary.recent_region_event_count,
                        )
                      }}</span>
                    </div>
                    <div class="feature-item">
                      <span class="feature-label">Recent Avg Mag</span>
                      <span class="feature-value">{{
                        safeDecimal(
                          detailData.feature_summary
                            .recent_region_avg_magnitude,
                        )
                      }}</span>
                    </div>
                    <div class="feature-item">
                      <span class="feature-label">Baseline Years</span>
                      <span class="feature-value">{{
                        safeValue(
                          detailData.feature_summary.historical_baseline_years,
                        )
                      }}</span>
                    </div>
                    <div class="feature-item">
                      <span class="feature-label">Anomaly Score</span>
                      <span class="feature-value">{{
                        safeDecimal(detailData.feature_summary.anomaly_score)
                      }}</span>
                    </div>
                  </div>
                </el-card>
              </div>

              <el-card shadow="never" class="detail-block detail-summary">
                <template #header>
                  <div class="detail-section-title">Assessment Summary</div>
                </template>
                <p class="detail-text">
                  {{
                    detailData.risk.explanation || "No explanation available."
                  }}
                </p>
              </el-card>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
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

function closeDetail() {
  detailVisible.value = false;
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
  background: linear-gradient(
    180deg,
    rgba(31, 45, 61, 0.95),
    rgba(22, 36, 56, 0.95)
  );
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease;
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
  gap: 22px;
  color: #e6edf5;
}

.detail-hero {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border: 1px solid #27405a;
  border-radius: 18px;
  background:
    radial-gradient(
      circle at top left,
      rgba(64, 158, 255, 0.14),
      transparent 38%
    ),
    linear-gradient(180deg, rgba(20, 34, 52, 0.98), rgba(14, 25, 39, 0.98));
}

.detail-hero-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.detail-hero-kicker {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6fa8dc;
}

.detail-hero-region {
  margin-top: 10px;
  font-size: 30px;
  line-height: 1.2;
  font-weight: 700;
  color: #f8fbff;
}

.detail-hero-time {
  margin-top: 10px;
  font-size: 18px;
  color: #95abc0;
}

.detail-hero-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(160px, 1fr));
  gap: 12px;
  flex-shrink: 0;
}

.hero-metric {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid #2d4965;
  background: rgba(12, 21, 34, 0.42);
}

.hero-metric-label {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #87a4c3;
}

.hero-metric-value {
  font-size: 30px;
  line-height: 1.15;
  font-weight: 800;
  color: #ffffff;
}

.hero-metric-score .hero-metric-value {
  color: #8ec5ff;
}

.detail-top-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(280px, 1fr);
  gap: 20px;
  align-items: stretch;
}

.detail-top-grid > .detail-block {
  height: 100%;
}

.detail-block {
  border: 1px solid #2c3e50;
  background-color: #162438;
  color: #e6edf5;
}

.detail-section-title {
  font-weight: 700;
  color: #f3f7fb;
  font-size: 22px;
}

.detail-summary :deep(.el-card__body) {
  padding-top: 10px;
}

.event-facts {
  display: grid;
  gap: 8px;
}

.event-fact {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  padding: 14px 2px;
  border-bottom: 1px solid rgba(49, 73, 97, 0.72);
}

.event-fact:last-child {
  border-bottom: none;
}

.event-fact-label {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #89a3bf;
}

.event-fact-value {
  font-size: 22px;
  line-height: 1.35;
  font-weight: 700;
  color: #f8fbff;
  word-break: break-word;
}

.detail-text {
  margin: 0;
  line-height: 1.85;
  font-size: 22px;
  color: #d7e0ea;
}

.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.detail-grid {
  height: 100%;
}

.feature-item {
  padding: 18px;
  border-radius: 12px;
  background: linear-gradient(
    180deg,
    rgba(31, 45, 61, 0.95),
    rgba(22, 36, 56, 0.95)
  );
  border: 1px solid #25384d;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: space-between;
}

.feature-label {
  font-size: 22px;
  color: #8aa0b8;
}

.feature-value {
  font-size: 22px;
  font-weight: 700;
  color: #f8fbff;
  line-height: 1.35;
  word-break: break-word;
}

.risk-detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 2200;
  background: rgba(2, 8, 18, 0.18);
  pointer-events: auto;
}

.risk-detail-panel {
  position: absolute;
  top: 50%;
  left: calc(360px + 36px);
  transform: translateY(-50%);
  width: min(860px, calc(100vw - 430px));
  max-height: calc(100vh - 64px);
  padding: 28px;
  overflow-y: auto;
  border-radius: 20px;
  border: 1px solid #25384d;
  background: linear-gradient(
    180deg,
    rgba(14, 24, 37, 0.97) 0%,
    rgba(17, 31, 49, 0.97) 100%
  );
  box-shadow: 0 24px 56px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(14px);
}

.risk-detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid #25384d;
}

.risk-detail-title {
  color: #f3f7fb;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.risk-detail-subtitle {
  margin-top: 6px;
  color: #8aa0b8;
  font-size: 20px;
}

.detail-close-btn {
  flex-shrink: 0;
  border-color: #35506a;
  background: rgba(22, 36, 56, 0.9);
  color: #d7e0ea;
  transform: scale(1.28);
}

.detail-close-btn:hover {
  border-color: #409eff;
  color: #ffffff;
  background: rgba(64, 158, 255, 0.16);
}

.risk-detail-panel :deep(.el-card__header) {
  border-bottom: 1px solid #25384d;
}

.risk-detail-panel :deep(.el-card__body) {
  background: transparent;
}

.risk-detail-panel :deep(.el-empty__description p) {
  color: #8aa0b8;
}

.risk-detail-fade-enter-active,
.risk-detail-fade-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}

.risk-detail-fade-enter-from,
.risk-detail-fade-leave-to {
  opacity: 0;
}

.risk-detail-fade-enter-from .risk-detail-panel,
.risk-detail-fade-leave-to .risk-detail-panel {
  transform: translateY(-50%) translateX(-10px);
}

@media (max-width: 1100px) {
  .risk-detail-panel {
    left: 50%;
    top: 52%;
    width: min(460px, calc(100vw - 32px));
    transform: translate(-50%, -50%);
  }

  .risk-detail-fade-enter-from .risk-detail-panel,
  .risk-detail-fade-leave-to .risk-detail-panel {
    transform: translate(-50%, -50%) translateY(10px);
  }

  .detail-hero {
    flex-direction: column;
  }

  .detail-hero-metrics {
    grid-template-columns: 1fr 1fr;
  }

  .detail-top-grid {
    grid-template-columns: 1fr;
  }
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
