import json, os, time
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

TREND_HOURS = 24

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Agent Budget Controller</title>
<style>
:root {
  --surface-1:      #fcfcfb;
  --page-plane:     #f9f9f7;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --gridline:       #e1e0d9;
  --border:         rgba(11,11,11,0.10);
  --good:    #0ca30c;
  --warning: #fab219;
  --serious: #ec835a;
  --critical:#d03b3b;
  --series-1: #2a78d6;
  --deemph:   #c3c2b7;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1:      #1a1a19;
    --page-plane:     #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --gridline:       #2c2c2a;
    --border:         rgba(255,255,255,0.10);
    --good:    #0ca30c;
    --warning: #fab219;
    --serious: #ec835a;
    --critical:#d03b3b;
    --series-1: #3987e5;
    --deemph:   #383835;
  }
}
* { box-sizing: border-box; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page-plane); color: var(--text-primary);
  margin: 0; padding: 28px; font-variant-numeric: tabular-nums;
}
h1 { font-size: 20px; font-weight: 700; margin: 0 0 2px; letter-spacing: -0.01em; font-variant-numeric: normal; }
.subtitle { color: var(--text-secondary); font-size: 13px; margin: 0 0 20px; }
.subtitle .dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--good); margin-right:6px; }

.stat-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-tile {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px;
}
.stat-tile .label { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted); margin-bottom: 6px; }
.stat-tile .value { font-size: 22px; font-weight: 700; line-height: 1; font-variant-numeric: normal; }
.stat-tile.good .value { color: var(--good); }
.stat-tile.warning .value { color: var(--warning); }
.stat-tile.critical .value { color: var(--critical); }

.card {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  margin-bottom: 16px; overflow: hidden;
}
.card-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--gridline); }
.card-head .name { font-size: 15px; font-weight: 700; }
.card-head .sub { color: var(--text-muted); font-size: 12px; margin-left: 8px; font-weight: 400; }
.card-body { padding: 8px 18px 4px; }
.table-toggle { background: none; border: none; color: var(--series-1); font-size: 12px; cursor: pointer; padding: 0; margin: 6px 0 12px; }
.table-toggle:hover { text-decoration: underline; }
.raw-table { display: none; margin: 0 0 12px; }
.raw-table.open { display: block; }
.raw-table table { width: 100%; border-collapse: collapse; }
.raw-table th, .raw-table td { padding: 5px 8px; font-size: 11px; border-bottom: 1px solid var(--gridline); text-align: right; }
.raw-table th:first-child, .raw-table td:first-child { text-align: left; }

.chart-wrap { position: relative; }
.chart-tip {
  position: absolute; pointer-events: none; background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 10px; font-size: 12px; box-shadow: 0 2px 10px rgba(0,0,0,.12); white-space: nowrap;
}
.chart-tip .v { font-weight: 700; font-size: 13px; color: var(--text-primary); }
.chart-tip .l { color: var(--text-muted); font-size: 11px; }

.team-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--gridline); gap: 16px; }
.team-head .name { font-size: 15px; font-weight: 700; }
.team-head .sub { color: var(--text-muted); font-size: 12px; margin-left: 8px; font-weight: 400; }
.team-head .figures { text-align: right; font-size: 13px; color: var(--text-secondary); white-space: nowrap; }
.team-head .figures b { color: var(--text-primary); font-weight: 700; }
.team-kpis { display: flex; gap: 18px; padding: 10px 18px 2px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }
.team-kpis b { color: var(--text-primary); }
.meter-track { height: 6px; border-radius: 3px; background: var(--gridline); overflow: hidden; margin-top: 8px; width: 200px; }
.meter-fill { height: 100%; border-radius: 3px; }
.spark { display: block; }

table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 10px 18px; border-bottom: 1px solid var(--gridline); font-size: 13px; }
th { color: var(--text-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; }
tr:last-child td { border-bottom: none; }
.agent-row { cursor: pointer; }
.agent-row:hover { background: color-mix(in srgb, var(--series-1) 6%, transparent); }
.agent-name { font-weight: 600; }
.chev { display: inline-block; width: 14px; color: var(--text-muted); transition: transform .15s; }
.chev.open { transform: rotate(90deg); }

.bar-bg { background: var(--gridline); border-radius: 5px; height: 8px; width: 120px; overflow: hidden; display: inline-block; vertical-align: middle; }
.bar-fill { height: 100%; border-radius: 5px; }
.pct-label { color: var(--text-muted); font-size: 12px; margin-left: 8px; }

.badge { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 20px; }
.badge .icon { font-size: 10px; line-height: 1; }
.badge.healthy  { color: var(--good);     background: color-mix(in srgb, var(--good) 14%, transparent); }
.badge.warning  { color: var(--warning);  background: color-mix(in srgb, var(--warning) 18%, transparent); }
.badge.exhausted{ color: var(--serious);  background: color-mix(in srgb, var(--serious) 16%, transparent); }
.badge.paused   { color: var(--critical); background: color-mix(in srgb, var(--critical) 14%, transparent); }

.detail-wrap { padding: 10px 18px 18px 44px; }
.kpi-strip { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 14px; }
.kpi { background: var(--page-plane); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
.kpi .l { font-size: 10px; text-transform: uppercase; letter-spacing: .03em; color: var(--text-muted); margin-bottom: 3px; }
.kpi .v { font-size: 14px; font-weight: 700; }
.kpi .v.crit { color: var(--critical); }
.kpi .v.warn { color: var(--warning); }

.sessions-wrap table { background: transparent; }
.sessions-wrap th, .sessions-wrap td { padding: 6px 12px; font-size: 12px; }
.empty { color: var(--text-muted); font-size: 12px; padding: 4px 12px; }
.model-chip {
  display: inline-block; font-size: 11px; color: var(--text-secondary);
  background: var(--page-plane); border: 1px solid var(--border); border-radius: 6px; padding: 2px 6px; margin-right: 4px;
}
.session-bar-row { display: flex; align-items: center; gap: 8px; padding: 4px 12px; font-size: 12px; }
.session-bar-row .sid { width: 160px; flex-shrink: 0; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-bar-track { flex: 1; background: var(--gridline); border-radius: 4px; height: 14px; overflow: hidden; }
.session-bar-fill { height: 100%; border-radius: 4px; background: var(--series-1); }
.session-bar-val { width: 90px; text-align: right; flex-shrink: 0; font-weight: 600; }
</style>
</head>
<body>
<h1>Agent Budget Controller</h1>
<p class="subtitle"><span class="dot"></span><span id="lastUpdated">Loading...</span></p>

<div class="stat-row" id="statRow"></div>

<div class="card">
  <div class="card-head"><span class="name">Organization spend &mdash; last 24 hours</span><span class="sub" id="orgTrendSub"></span></div>
  <div class="card-body">
    <div class="chart-wrap" id="orgChart"></div>
    <button class="table-toggle" id="orgTableToggle">View as table</button>
    <div class="raw-table" id="orgTableWrap"></div>
  </div>
</div>

<div id="teams"></div>

<script>
function fmt(n) {
  n = n || 0;
  if (n === 0) return "$0.00";
  if (Math.abs(n) < 0.01) return "$" + n.toFixed(6);
  return "$" + n.toFixed(2);
}
function fmtHour(label) {
  // label: "YYYY-MM-DD-HH"
  var parts = label.split("-");
  var d = new Date(Date.UTC(+parts[0], +parts[1]-1, +parts[2], +parts[3]));
  return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
}
function timeAgo(ts) {
  if (!ts) return "never";
  var s = Math.max(0, Math.floor(Date.now()/1000) - ts);
  if (s < 60) return s + "s ago";
  if (s < 3600) return Math.floor(s/60) + "m ago";
  if (s < 86400) return Math.floor(s/3600) + "h ago";
  return Math.floor(s/86400) + "d ago";
}
function pctColor(pct, status) {
  if (status === "paused") return "var(--critical)";
  if (pct >= 100) return "var(--serious)";
  if (pct >= 80) return "var(--warning)";
  return "var(--good)";
}
function statusBadge(status) {
  var map = {
    healthy:   ["\\u25CF", "Healthy"],
    warning:   ["\\u25B2", "Warning"],
    exhausted: ["\\u25A0", "Exhausted"],
    paused:    ["\\u26D4", "Paused"],
  };
  var m = map[status] || ["\\u25CF", status];
  return "<span class='badge " + status + "'><span class='icon'>" + m[0] + "</span>" + m[1] + "</span>";
}
function meterBar(pct, status, width) {
  var clamped = Math.min(pct, 100);
  var color = pctColor(pct, status);
  return "<div class='bar-bg' style='width:" + (width || 120) + "px'>" +
         "<div class='bar-fill' style='width:" + clamped + "%; background:" + color + "'></div></div>" +
         "<span class='pct-label'>" + pct + "%</span>";
}

// ---- Sparkline (small multiples, non-interactive: values are already shown as KPI numbers) ----
function sparklineSvg(values, w, h) {
  w = w || 200; h = h || 36;
  var max = Math.max.apply(null, values.concat([0.000001]));
  var n = values.length;
  var stepX = w / (n - 1 || 1);
  var pts = values.map(function (v, i) {
    var x = i * stepX;
    var y = h - (v / max) * (h - 4) - 2;
    return x.toFixed(1) + "," + y.toFixed(1);
  });
  var d = "M" + pts.join(" L");
  return "<svg class='spark' viewBox='0 0 " + w + " " + h + "' preserveAspectRatio='none' style='width:" + w + "px;height:" + h + "px'>" +
         "<path d='" + d + "' fill='none' stroke='var(--series-1)' stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/>" +
         "</svg>";
}

// ---- Main interactive trend chart: crosshair + tooltip + table-view twin ----
function renderTrendChart(mountId, hourLabels, values) {
  var w = 760, h = 200, padL = 46, padR = 12, padT = 14, padB = 26;
  var plotW = w - padL - padR, plotH = h - padT - padB;
  var max = Math.max.apply(null, values.concat([0.000001]));
  var n = values.length;
  var stepX = n > 1 ? plotW / (n - 1) : 0;
  function xAt(i) { return padL + i * stepX; }
  function yAt(v) { return padT + plotH - (v / max) * plotH; }
  var pathD = values.map(function (v, i) { return (i === 0 ? "M" : "L") + xAt(i).toFixed(1) + "," + yAt(v).toFixed(1); }).join(" ");

  var ticks = [0, 0.5, 1].map(function (f) {
    var val = max * f, y = yAt(val);
    return "<line x1='" + padL + "' y1='" + y.toFixed(1) + "' x2='" + (w - padR) + "' y2='" + y.toFixed(1) + "' stroke='var(--gridline)' stroke-width='1'/>" +
           "<text x='" + (padL - 8) + "' y='" + (y + 4).toFixed(1) + "' text-anchor='end' font-size='10' fill='var(--text-muted)'>" + fmt(val) + "</text>";
  }).join("");

  var xLabelEvery = Math.ceil(n / 6);
  var xLabels = values.map(function (_, i) {
    if (i % xLabelEvery !== 0) return "";
    return "<text x='" + xAt(i).toFixed(1) + "' y='" + (h - 6) + "' text-anchor='middle' font-size='10' fill='var(--text-muted)'>" + fmtHour(hourLabels[i]) + "</text>";
  }).join("");

  var mount = document.getElementById(mountId);
  mount.innerHTML =
    "<svg viewBox='0 0 " + w + " " + h + "' preserveAspectRatio='none' style='width:100%;height:" + h + "px;display:block' id='" + mountId + "_svg'>" +
      ticks + xLabels +
      "<path d='" + pathD + "' fill='none' stroke='var(--series-1)' stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/>" +
      "<line id='" + mountId + "_cross' x1='0' y1='" + padT + "' x2='0' y2='" + (h - padB) + "' stroke='var(--text-muted)' stroke-width='1' style='display:none'/>" +
      "<circle id='" + mountId + "_dot' r='4' fill='var(--series-1)' stroke='var(--surface-1)' stroke-width='2' style='display:none'/>" +
      "<rect id='" + mountId + "_overlay' x='" + padL + "' y='0' width='" + plotW + "' height='" + h + "' fill='transparent'/>" +
    "</svg>" +
    "<div class='chart-tip' id='" + mountId + "_tip' style='display:none'></div>";

  var svg = document.getElementById(mountId + "_svg");
  var overlay = document.getElementById(mountId + "_overlay");
  var cross = document.getElementById(mountId + "_cross");
  var dot = document.getElementById(mountId + "_dot");
  var tip = document.getElementById(mountId + "_tip");

  function handleMove(clientX, clientY) {
    var rect = svg.getBoundingClientRect();
    var scaleX = w / rect.width;
    var localX = (clientX - rect.left) * scaleX;
    var idx = Math.round((localX - padL) / (stepX || 1));
    idx = Math.max(0, Math.min(n - 1, idx));
    var x = xAt(idx), y = yAt(values[idx]);
    cross.setAttribute("x1", x); cross.setAttribute("x2", x);
    cross.style.display = "block";
    dot.setAttribute("cx", x); dot.setAttribute("cy", y);
    dot.style.display = "block";
    var tipLeft = ((x / w) * rect.width) + 12;
    var tipTop = (clientY - rect.top) - 40;
    tip.style.left = Math.min(tipLeft, rect.width - 140) + "px";
    tip.style.top = Math.max(tipTop, 0) + "px";
    tip.innerHTML = "<div class='v'>" + fmt(values[idx]) + "</div><div class='l'>" + fmtHour(hourLabels[idx]) + "</div>";
    tip.style.display = "block";
  }
  overlay.addEventListener("pointermove", function (e) { handleMove(e.clientX, e.clientY); });
  overlay.addEventListener("pointerleave", function () {
    cross.style.display = "none"; dot.style.display = "none"; tip.style.display = "none";
  });
}

function renderOrgTable(hourLabels, values) {
  var rows = hourLabels.map(function (l, i) {
    return "<tr><td>" + fmtHour(l) + "</td><td>" + fmt(values[i]) + "</td></tr>";
  }).join("");
  document.getElementById("orgTableWrap").innerHTML =
    "<table><thead><tr><th>Hour</th><th>Spend</th></tr></thead><tbody>" + rows + "</tbody></table>";
}

var expanded = new Set();
var tableToggleWired = false;

function renderStats(s) {
  var tiles = [
    { label: "Total Spend", value: fmt(s.total_spend), cls: "" },
    { label: "Teams", value: s.total_teams, cls: "" },
    { label: "Agents", value: s.total_agents, cls: "" },
    { label: "Total Calls", value: s.total_calls, cls: "" },
    { label: "Avg Cost / Call", value: fmt(s.avg_cost_per_call), cls: "" },
    { label: "Paused / Warning", value: s.paused_count + "P / " + s.warning_count + "W", cls: (s.paused_count > 0 ? "critical" : (s.warning_count > 0 ? "warning" : "good")) },
  ];
  document.getElementById("statRow").innerHTML = tiles.map(function (t) {
    return "<div class='stat-tile " + t.cls + "'><div class='label'>" + t.label + "</div><div class='value'>" + t.value + "</div></div>";
  }).join("");
}

function renderSessions(agent) {
  if (!agent.sessions.length) {
    return "<div class='empty'>No sessions recorded yet.</div>";
  }
  var maxSess = Math.max.apply(null, agent.sessions.map(function (s) { return s.spend; }).concat([0.000001]));
  var bars = agent.sessions.length > 1 ? agent.sessions.map(function (sess) {
    var w = Math.max(2, (sess.spend / maxSess) * 100);
    return "<div class='session-bar-row'><div class='sid'>" + sess.id + "</div>" +
           "<div class='session-bar-track'><div class='session-bar-fill' style='width:" + w + "%'></div></div>" +
           "<div class='session-bar-val'>" + fmt(sess.spend) + "</div></div>";
  }).join("") : "";
  var rows = agent.sessions.map(function (sess) {
    return "<tr><td>" + sess.id + "</td><td>" + fmt(sess.spend) + "</td><td>" + sess.calls + "</td>" +
           "<td>" + fmt(sess.avg_cost_per_call) + "</td>" +
           "<td><span class='model-chip'>" + (sess.last_model || "-") + "</span></td>" +
           "<td>" + timeAgo(sess.last_active_ts) + "</td></tr>";
  }).join("");
  return (bars ? "<div style='margin-bottom:10px'>" + bars + "</div>" : "") +
         "<div class='sessions-wrap'><table><thead><tr><th>Session</th><th>Spend</th><th>Calls</th><th>Avg/Call</th><th>Last Model</th><th>Last Active</th></tr></thead>" +
         "<tbody>" + rows + "</tbody></table></div>";
}

function renderAgentDetail(agent) {
  var kpis = [
    { l: "Remaining Budget", v: fmt(agent.remaining_budget), cls: "" },
    { l: "Burn Rate / Day", v: fmt(agent.burn_rate_day), cls: "" },
    { l: "Days Left @ Rate", v: agent.days_left === null ? "\\u2014" : agent.days_left, cls: (agent.days_left !== null && agent.days_left < 3 ? "crit" : "") },
    { l: "Total Calls", v: agent.total_calls, cls: "" },
    { l: "This Hour", v: fmt(agent.spend_hour) + " / " + fmt(agent.runaway_threshold), cls: (agent.spend_hour >= agent.runaway_threshold ? "crit" : "") },
    { l: "Last Active", v: timeAgo(agent.last_active_ts), cls: "" },
  ];
  var kpiHtml = kpis.map(function (k) {
    return "<div class='kpi'><div class='l'>" + k.l + "</div><div class='v " + k.cls + "'>" + k.v + "</div></div>";
  }).join("");
  return (
    "<div class='detail-wrap'>" +
      "<div class='kpi-strip'>" + kpiHtml + "</div>" +
      sparklineSvg(agent.trend, 300, 40) +
      "<div style='margin-top:12px'>" + renderSessions(agent) + "</div>" +
    "</div>"
  );
}

function renderTeams(teams) {
  document.getElementById("teams").innerHTML = teams.map(function (team) {
    var agentRows = team.agents.map(function (agent) {
      var isOpen = expanded.has(agent.id);
      var models = Object.keys(agent.model_spend || {}).map(function (m) {
        return "<span class='model-chip'>" + m + ": " + fmt(agent.model_spend[m]) + "</span>";
      }).join("");
      var row =
        "<tr class='agent-row' data-agent='" + agent.id + "'>" +
          "<td><span class='chev" + (isOpen ? " open" : "") + "'>\\u25B8</span><span class='agent-name'>" + agent.id + "</span></td>" +
          "<td>" + fmt(agent.spend) + "</td>" +
          "<td>" + fmt(agent.limit) + "</td>" +
          "<td>" + meterBar(agent.pct, agent.status) + "</td>" +
          "<td>" + statusBadge(agent.status) + "</td>" +
          "<td>" + (models || "<span class='empty'>-</span>") + "</td>" +
          "<td>" + agent.session_count + "</td>" +
          "<td>" + agent.total_calls + "</td>" +
        "</tr>";
      if (isOpen) {
        row += "<tr><td colspan='8' style='padding:0;border-bottom:1px solid var(--gridline)'>" + renderAgentDetail(agent) + "</td></tr>";
      }
      return row;
    }).join("");

    return (
      "<div class='card'>" +
        "<div class='team-head'>" +
          "<div><span class='name'>" + team.id + "</span><span class='sub'>" + team.agent_count + " agent" + (team.agent_count === 1 ? "" : "s") + "</span>" +
            "<div class='meter-track'><div class='meter-fill' style='width:" + Math.min(team.pct, 100) + "%; background:" + pctColor(team.pct, "team") + "'></div></div>" +
          "</div>" +
          sparklineSvg(team.trend, 160, 34) +
          "<div class='figures'><b>" + fmt(team.spend) + "</b> / " + fmt(team.limit) + " &middot; " + team.pct + "%</div>" +
        "</div>" +
        "<div class='team-kpis'><span>Calls: <b>" + team.total_calls + "</b></span><span>Avg/Call: <b>" + fmt(team.avg_cost_per_call) + "</b></span></div>" +
        "<table><thead><tr><th>Agent</th><th>Spend</th><th>Limit</th><th>% Used</th><th>Status</th><th>Model Breakdown</th><th>Sessions</th><th>Calls</th></tr></thead>" +
        "<tbody>" + agentRows + "</tbody></table>" +
      "</div>"
    );
  }).join("");

  document.querySelectorAll(".agent-row").forEach(function (row) {
    row.addEventListener("click", function () {
      var id = row.getAttribute("data-agent");
      if (expanded.has(id)) { expanded.delete(id); } else { expanded.add(id); }
      loadData();
    });
  });
}

async function loadData() {
  try {
    var dataUrl = window.location.pathname + "/data";
    var res = await fetch(dataUrl);
    var payload = await res.json();
    renderStats(payload.summary);
    renderTrendChart("orgChart", payload.hour_labels, payload.summary.trend);
    renderOrgTable(payload.hour_labels, payload.summary.trend);
    renderTeams(payload.teams);
    if (!tableToggleWired) {
      document.getElementById("orgTableToggle").addEventListener("click", function (e) {
        var wrap = document.getElementById("orgTableWrap");
        wrap.classList.toggle("open");
        e.target.textContent = wrap.classList.contains("open") ? "Hide table" : "View as table";
      });
      tableToggleWired = true;
    }
    document.getElementById("lastUpdated").textContent = "Live \\u2014 last updated " + new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById("lastUpdated").textContent = "Error loading data: " + e;
  }
}
loadData();
setInterval(loadData, 10000);
</script>
</body>
</html>"""


def handler(event, context):
    path = event.get("path", "") or ""
    if path.endswith("/data"):
        return get_data()
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": HTML_PAGE,
    }


def agent_status(item, pct):
    if item.get("status") == "PAUSED":
        return "paused"
    if pct >= 100:
        return "exhausted"
    if pct >= 80:
        return "warning"
    return "healthy"


def hour_series_labels(now_ts):
    return [time.strftime("%Y-%m-%d-%H", time.gmtime(now_ts - h * 3600)) for h in range(TREND_HOURS - 1, -1, -1)]


def agent_hourly_series(agent_id, hour_labels):
    oldest, newest = hour_labels[0], hour_labels[-1]
    items = table.query(
        KeyConditionExpression=Key("PK").eq(f"AGENT#{agent_id}") & Key("SK").between(f"HOUR#{oldest}", f"HOUR#{newest}")
    ).get("Items", [])
    by_hour = {it["SK"].split("#", 1)[1]: float(it.get("spend", 0)) for it in items}
    return [round(by_hour.get(h, 0.0), 6) for h in hour_labels]


def get_data():
    now_ts = int(time.time())
    hour_labels = hour_series_labels(now_ts)

    items = table.scan().get("Items", [])
    team_items, agent_items, session_items = [], [], []
    for it in items:
        pk, sk = it["PK"], it["SK"]
        if pk.startswith("TEAM#") and sk == "PERIOD#current":
            team_items.append(it)
        elif pk.startswith("AGENT#") and sk == "PERIOD#current":
            agent_items.append(it)
        elif pk.startswith("AGENT#") and sk.startswith("SESSION#"):
            session_items.append(it)

    sessions_by_agent = {}
    for it in session_items:
        agent_id = it["PK"].split("#", 1)[1]
        calls = int(it.get("call_count", 0))
        spend = float(it.get("spend_total", 0))
        sessions_by_agent.setdefault(agent_id, []).append({
            "id": it["SK"].split("#", 1)[1],
            "spend": spend,
            "calls": calls,
            "avg_cost_per_call": round(spend / calls, 6) if calls else 0.0,
            "last_model": it.get("last_model", ""),
            "last_active_ts": int(it.get("last_active_ts", 0)),
        })
    for sess_list in sessions_by_agent.values():
        sess_list.sort(key=lambda s: s["last_active_ts"], reverse=True)

    agents_by_team = {}
    org_trend = [0.0] * TREND_HOURS
    summary = {"total_spend": 0.0, "total_agents": 0, "total_teams": 0,
               "healthy_count": 0, "warning_count": 0, "exhausted_count": 0, "paused_count": 0,
               "total_calls": 0}

    for it in agent_items:
        agent_id = it["PK"].split("#", 1)[1]
        team_id = it.get("team_id", "unassigned")
        spend = float(it.get("spend_month", 0))
        limit = float(it.get("limit_month", 1)) or 1
        pct = round(min(spend / limit, 2.0) * 100, 1)
        status = agent_status(it, pct)

        sessions = sessions_by_agent.get(agent_id, [])
        total_calls = sum(s["calls"] for s in sessions)
        avg_cost = round(spend / total_calls, 6) if total_calls else 0.0
        trend = agent_hourly_series(agent_id, hour_labels)
        burn_rate_day = round(sum(trend), 6)
        remaining = round(max(limit - spend, 0.0), 6)
        days_left = round(remaining / burn_rate_day, 1) if burn_rate_day > 0 else None

        summary["total_spend"] += spend
        summary["total_agents"] += 1
        summary["total_calls"] += total_calls
        summary[f"{status}_count"] += 1
        for i in range(TREND_HOURS):
            org_trend[i] += trend[i]

        agents_by_team.setdefault(team_id, []).append({
            "id": agent_id, "spend": spend, "limit": limit, "pct": pct, "status": status,
            "model_spend": {k: float(v) for k, v in it.get("model_spend", {}).items()},
            "sessions": sessions, "session_count": len(sessions),
            "total_calls": total_calls, "avg_cost_per_call": avg_cost,
            "remaining_budget": remaining, "burn_rate_day": burn_rate_day, "days_left": days_left,
            "spend_hour": float(it.get("spend_hour", 0)), "runaway_threshold": round(0.2 * limit, 6),
            "last_active_ts": int(it.get("last_active_ts", 0)),
            "trend": trend,
        })

    teams = []
    for it in team_items:
        team_id = it["PK"].split("#", 1)[1]
        spend = float(it.get("spend_month", 0))
        limit = float(it.get("limit_month", 1)) or 1
        pct = round(min(spend / limit, 2.0) * 100, 1)
        agents = sorted(agents_by_team.get(team_id, []), key=lambda a: a["id"])
        team_calls = sum(a["total_calls"] for a in agents)
        team_avg = round(spend / team_calls, 6) if team_calls else 0.0
        team_trend = [0.0] * TREND_HOURS
        for a in agents:
            for i in range(TREND_HOURS):
                team_trend[i] += a["trend"][i]
        teams.append({
            "id": team_id, "spend": spend, "limit": limit, "pct": pct,
            "agent_count": len(agents), "agents": agents,
            "total_calls": team_calls, "avg_cost_per_call": team_avg,
            "trend": [round(v, 6) for v in team_trend],
        })
    summary["total_teams"] = len(teams)
    summary["avg_cost_per_call"] = round(summary["total_spend"] / summary["total_calls"], 6) if summary["total_calls"] else 0.0
    summary["trend"] = [round(v, 6) for v in org_trend]
    teams.sort(key=lambda t: t["id"])

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"generated_at": now_ts, "hour_labels": hour_labels, "summary": summary, "teams": teams}),
    }
