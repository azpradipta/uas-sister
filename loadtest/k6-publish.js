import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const targetUrl = __ENV.TARGET_URL || "http://localhost:8080/publish";
const batchSize = Number(__ENV.BATCH_SIZE || "100");
const duplicateRate = Math.min(Math.max(Number(__ENV.DUPLICATE_RATE || "0.30"), 0), 0.95);
const source = __ENV.SOURCE || "k6-load";
const topics = (__ENV.TOPICS || "auth.login,payments,inventory,system.metrics")
  .split(",")
  .map((topic) => topic.trim())
  .filter(Boolean);

export const publishLatency = new Trend("publish_latency_ms");
export const publishErrors = new Rate("publish_errors");

export const options = {
  scenarios: {
    publish_load: {
      executor: "constant-arrival-rate",
      rate: Number(__ENV.K6_RATE || "4"),
      timeUnit: "1s",
      duration: __ENV.K6_DURATION || "1m",
      preAllocatedVUs: Number(__ENV.K6_PRE_ALLOCATED_VUS || "20"),
      maxVUs: Number(__ENV.K6_MAX_VUS || "100"),
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1000"],
    publish_errors: ["rate<0.05"],
  },
};

function buildBatch() {
  const uniqueCount = Math.max(1, Math.floor(batchSize * (1 - duplicateRate)));
  const duplicateCount = Math.max(0, batchSize - uniqueCount);
  const baseKey = `${source}-vu${__VU}-iter${__ITER}`;
  const uniqueEvents = [];

  for (let index = 0; index < uniqueCount; index += 1) {
    const topic = topics[(index + __ITER) % topics.length];
    uniqueEvents.push({
      topic,
      event_id: `${baseKey}-${index}`,
      timestamp: new Date().toISOString(),
      source,
      payload: {
        seq: index,
        level: index % 10 === 0 ? "WARN" : "INFO",
        message: `k6 generated log ${index}`,
        duplicate_replay: false,
      },
    });
  }

  const duplicateEvents = [];
  for (let index = 0; index < duplicateCount; index += 1) {
    const original = uniqueEvents[index % uniqueEvents.length];
    duplicateEvents.push({
      ...original,
      payload: {
        ...original.payload,
        duplicate_replay: true,
        replay_index: index,
      },
    });
  }

  return uniqueEvents.concat(duplicateEvents);
}

export default function () {
  const payload = JSON.stringify(buildBatch());
  const response = http.post(targetUrl, payload, {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "publish" },
  });

  publishLatency.add(response.timings.duration);
  const ok = check(response, {
    "publish status is 200": (res) => res.status === 200,
    "publish response has queued": (res) => {
      try {
        return Number(res.json("queued")) === batchSize;
      } catch (_) {
        return false;
      }
    },
  });

  publishErrors.add(!ok);
  sleep(Number(__ENV.K6_SLEEP_SECONDS || "0"));
}
