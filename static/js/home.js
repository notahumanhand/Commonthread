(() => {
    const $ = (id) => document.getElementById(id);
    const filterIds = ["start-date", "end-date", "academic-unit", "cohort", "campaign", "gift-type", "metric", "granularity"];
    let latestData = null;
    let latestOptions = null;

    const metricLabels = {
        unique_donors: "Unique donors",
        first_time_donors: "First-time donors",
        total_giving: "Total giving",
        amount_per_donor: "Amount per donor",
        gifts_per_donor: "Gifts per donor",
    };

    function money(cents, digits = 0) {
        if (cents === null || cents === undefined) return "N/A";
        return new Intl.NumberFormat("en-US", {
            style: "currency", currency: "USD", maximumFractionDigits: digits,
            minimumFractionDigits: digits,
        }).format(cents / 100);
    }

    function number(value, digits = 0) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
        return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (character) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
        })[character]);
    }

    function queryString() {
        const params = new URLSearchParams();
        params.set("start_date", $("start-date").value);
        params.set("end_date", $("end-date").value);
        params.set("academic_unit", $("academic-unit").value);
        params.set("cohort", $("cohort").value);
        params.set("campaign", $("campaign").value);
        params.set("gift_type", $("gift-type").value);
        params.set("metric", $("metric").value);
        params.set("granularity", $("granularity").value);
        return params.toString();
    }

    async function loadOptions() {
        const response = await fetch("/api/dashboard/options");
        if (!response.ok) throw new Error("Could not load dashboard filter options.");
        latestOptions = await response.json();
        const unitSelect = $("academic-unit");
        const campaignSelect = $("campaign");
        latestOptions.academic_units.forEach((unit) => {
            const option = document.createElement("option");
            option.value = unit.id;
            option.textContent = unit.name;
            unitSelect.append(option);
        });
        latestOptions.campaigns.forEach((campaign) => {
            const option = document.createElement("option");
            option.value = campaign.id;
            option.textContent = campaign.name;
            campaignSelect.append(option);
        });
        $("start-date").min = latestOptions.min_date;
        $("start-date").max = latestOptions.max_date;
        $("end-date").min = latestOptions.min_date;
        $("end-date").max = latestOptions.max_date;
        if ($("start-date").value < latestOptions.min_date) $("start-date").value = latestOptions.min_date;
        if ($("end-date").value > latestOptions.max_date) $("end-date").value = latestOptions.max_date;
    }

    async function refreshDashboard() {
        const status = $("chart-status");
        status.textContent = "Loading dashboard data…";
        status.classList.remove("is-error");
        try {
            const response = await fetch(`/api/dashboard?${queryString()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Dashboard data could not be loaded.");
            latestData = data;
            renderSummary(data.summary);
            renderChart(data.series, data.campaigns, data.filters);
            renderCampaigns(data.campaigns);
            renderTransactions(data.transactions);
            renderFilterSummary(data.filters);
            status.textContent = data.series.length ? `${data.series.length} time periods · ${number(data.summary.gift_count)} qualifying gifts` : "No qualifying gifts match these filters.";
        } catch (error) {
            status.textContent = error.message;
            status.classList.add("is-error");
            $("gift-table-body").innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(error.message)}</td></tr>`;
        }
    }

    function renderSummary(summary) {
        $("kpi-giving").textContent = money(summary.giving_cents);
        $("kpi-donors").textContent = number(summary.donors);
        $("kpi-first-time").textContent = number(summary.first_time_donors);
        $("kpi-frequency").textContent = number(summary.gifts_per_donor, 2);
        $("kpi-gifts-note").textContent = `${number(summary.gift_count)} qualifying gifts`;
    }

    function renderFilterSummary(filters) {
        const parts = [`${filters.start_date} to ${filters.end_date}`, metricLabels[filters.metric], filters.granularity];
        if (filters.academic_unit_id !== "all") parts.push($("academic-unit").selectedOptions[0]?.textContent || "Academic unit");
        if (filters.cohort !== "all") parts.push($("cohort").selectedOptions[0]?.textContent || "Cohort");
        if (filters.campaign_id !== "all") parts.push($("campaign").selectedOptions[0]?.textContent || "Campaign");
        if (filters.gift_type !== "all") parts.push($("gift-type").selectedOptions[0]?.textContent || "Gift type");
        $("active-filter-summary").textContent = `Current view: ${parts.join(" · ")}`;
    }

    function svgNode(name, attrs = {}, text = null) {
        const node = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
        if (text !== null) node.textContent = text;
        return node;
    }

    function formatMetric(value, metric) {
        if (value === null || value === undefined) return "N/A";
        if (metric === "total_giving" || metric === "amount_per_donor") return money(value * 100, 0);
        return number(value, metric === "gifts_per_donor" ? 2 : 0);
    }

    function renderChart(series, campaigns, filters) {
        const svg = $("trend-chart");
        svg.replaceChildren();
        $("chart-legend-label").textContent = metricLabels[filters.metric];
        const width = 1000, height = 390;
        const margin = { top: 28, right: 30, bottom: 70, left: 82 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;
        if (!series.length) {
            svg.append(svgNode("text", { x: width / 2, y: height / 2, "text-anchor": "middle", class: "svg-empty" }, "No data for this selection"));
            return;
        }
        const values = series.map((point) => Number(point.value ?? 0));
        const maxValue = Math.max(...values, 1);
        const yMax = maxValue * 1.15;
        const xAt = (index) => margin.left + (series.length === 1 ? plotWidth / 2 : index * plotWidth / (series.length - 1));
        const yAt = (value) => margin.top + plotHeight - (Number(value ?? 0) / yMax) * plotHeight;

        for (let i = 0; i <= 4; i += 1) {
            const y = margin.top + plotHeight - (i / 4) * plotHeight;
            svg.append(svgNode("line", { x1: margin.left, x2: width - margin.right, y1: y, y2: y, class: "chart-gridline" }));
            const tickValue = yMax * i / 4;
            const tickText = (filters.metric === "total_giving" || filters.metric === "amount_per_donor")
                ? money(tickValue * 100)
                : number(tickValue, filters.metric === "gifts_per_donor" ? 1 : 0);
            svg.append(svgNode("text", { x: margin.left - 12, y: y + 4, "text-anchor": "end", class: "chart-axis-label" }, tickText));
        }

        if ($("show-campaigns").checked) {
            const start = new Date(`${filters.start_date}T00:00:00Z`).getTime();
            const end = new Date(`${filters.end_date}T23:59:59Z`).getTime();
            const span = Math.max(end - start, 1);
            campaigns.filter((campaign) => campaign.end_date >= filters.start_date && campaign.start_date <= filters.end_date).forEach((campaign, index) => {
                const campaignStart = new Date(`${campaign.start_date}T00:00:00Z`).getTime();
                const campaignEnd = new Date(`${campaign.end_date}T23:59:59Z`).getTime();
                const left = margin.left + Math.max(0, campaignStart - start) / span * plotWidth;
                const right = margin.left + Math.min(span, campaignEnd - start) / span * plotWidth;
                const x = Math.max(margin.left, left);
                const rectWidth = Math.max(2, Math.min(width - margin.right, right) - x);
                svg.append(svgNode("rect", { x, y: margin.top, width: rectWidth, height: plotHeight, class: `campaign-band campaign-band-${index % 5}`, opacity: 0.15 }));
                if (rectWidth > 34) {
                    const label = svgNode("text", { x: x + 4, y: margin.top + 12 + (index % 3) * 13, class: "campaign-band-label" }, campaign.name);
                    label.setAttribute("transform", `translate(0 0)`);
                    svg.append(label);
                }
            });
        }

        series.forEach((point, index) => {
            const x = xAt(index);
            svg.append(svgNode("text", { x, y: height - margin.bottom + 24, "text-anchor": "middle", class: "chart-axis-label", transform: `rotate(-35 ${x} ${height - margin.bottom + 24})` }, point.period));
        });
        const path = series.map((point, index) => `${index === 0 ? "M" : "L"} ${xAt(index)} ${yAt(point.value)}`).join(" ");
        svg.append(svgNode("path", { d: path, class: "chart-line" }));
        series.forEach((point, index) => {
            const circle = svgNode("circle", { cx: xAt(index), cy: yAt(point.value), r: 5, class: "chart-point", tabindex: 0, role: "button", "aria-label": `${point.period}: ${formatMetric(point.value, filters.metric)}. Select to view supporting gifts.` });
            const title = svgNode("title", {}, `${point.period}: ${formatMetric(point.value, filters.metric)} · ${number(point.gift_count)} gifts · ${number(point.donors)} donors`);
            circle.append(title);
            const selectPoint = () => showPointDetails(point, filters);
            circle.addEventListener("click", selectPoint);
            circle.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectPoint(); } });
            svg.append(circle);
        });
        svg.append(svgNode("line", { x1: margin.left, x2: margin.left, y1: margin.top, y2: margin.top + plotHeight, class: "chart-axis" }));
        svg.append(svgNode("line", { x1: margin.left, x2: width - margin.right, y1: margin.top + plotHeight, y2: margin.top + plotHeight, class: "chart-axis" }));
    }

    async function showPointDetails(point, filters) {
        $("detail-heading").textContent = `Gifts for ${point.period}`;
        $("detail-description").textContent = `${formatMetric(point.value, filters.metric)} ${metricLabels[filters.metric].toLowerCase()} · ${number(point.gift_count)} qualifying gifts · ${number(point.donors)} distinct donors. Loading supporting transactions…`;
        $("detail-panel").scrollIntoView({ behavior: "smooth", block: "start" });
        const period = periodBounds(point.period, filters.granularity);
        const params = new URLSearchParams(queryString());
        params.set("period_start", period.start);
        params.set("period_end", period.end);
        try {
            const response = await fetch(`/api/dashboard/transactions?${params.toString()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Could not load supporting transactions.");
            renderTransactions(data.transactions);
            $("detail-description").textContent = `${formatMetric(point.value, filters.metric)} ${metricLabels[filters.metric].toLowerCase()} · ${number(point.gift_count)} qualifying gifts · ${number(point.donors)} distinct donors. Showing up to 25 gifts from ${period.start} through ${period.end}.`;
        } catch (error) {
            $("detail-description").textContent = error.message;
        }
    }

    function periodBounds(period, granularity) {
        if (granularity === "month") {
            const [year, month] = period.split("-").map(Number);
            const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
            return { start: `${period}-01`, end: `${period}-${String(lastDay).padStart(2, "0")}` };
        }
        if (granularity === "quarter") {
            const match = period.match(/^FY(\d{4}) Q([1-4])$/);
            if (match) {
                const fy = Number(match[1]);
                const q = Number(match[2]);
                const starts = ["07-01", "10-01", "01-01", "04-01"];
                const ends = ["09-30", "12-31", "03-31", "06-30"];
                const year = q <= 2 ? fy - 1 : fy;
                const endYear = q <= 2 ? fy - 1 : fy;
                return { start: `${year}-${starts[q - 1]}`, end: `${endYear}-${ends[q - 1]}` };
            }
        }
        const yearMatch = period.match(/^FY(\d{4})$/);
        if (yearMatch) {
            const fy = Number(yearMatch[1]);
            return { start: `${fy - 1}-07-01`, end: `${fy}-06-30` };
        }
        return { start: $("start-date").value, end: $("end-date").value };
    }

    function renderCampaigns(campaigns) {
        const container = $("campaign-list");
        container.replaceChildren();
        campaigns.forEach((campaign) => {
            const row = document.createElement("div");
            row.className = "campaign-row";
            const percent = Math.max(0, Math.min(100, campaign.attainment * 100));
            row.innerHTML = `<div class="campaign-row-top"><strong>${escapeHtml(campaign.name)}</strong><span>${number(campaign.attainment * 100, 1)}%</span></div>
                <div class="campaign-meta">${escapeHtml(campaign.start_date)} – ${escapeHtml(campaign.end_date)}</div>
                <div class="campaign-progress" role="img" aria-label="${number(campaign.attainment * 100, 1)} percent of goal"><span style="width:${percent}%"></span></div>
                <div class="campaign-row-bottom"><span>${money(campaign.attributed_cents)} attributed</span><span>Goal ${money(campaign.goal_cents)}</span></div>`;
            row.addEventListener("click", () => {
                $("campaign").value = campaign.id;
                refreshDashboard();
                window.scrollTo({ top: 0, behavior: "smooth" });
            });
            row.tabIndex = 0;
            row.setAttribute("role", "button");
            row.setAttribute("aria-label", `Filter dashboard to ${campaign.name}`);
            row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); row.click(); } });
            container.append(row);
        });
    }

    function renderTransactions(transactions) {
        const tbody = $("gift-table-body");
        if (!transactions.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">No qualifying gifts match these filters.</td></tr>';
            return;
        }
        tbody.innerHTML = transactions.map((gift) => `<tr>
            <td>${escapeHtml(gift.gift_date)}</td><td>${escapeHtml(gift.donor_name)}</td><td>${escapeHtml(gift.unit_name)}</td>
            <td>${escapeHtml(gift.campaign_name || "—")}</td><td class="amount-cell">${money(gift.amount_cents)}</td></tr>`).join("");
    }

    function resetFilters() {
        if (!latestOptions) return;
        $("start-date").value = latestOptions.min_date;
        $("end-date").value = latestOptions.max_date;
        $("academic-unit").value = "all";
        $("cohort").value = "all";
        $("campaign").value = "all";
        $("gift-type").value = "all";
        $("metric").value = "unique_donors";
        $("granularity").value = "month";
        $("show-campaigns").checked = true;
        refreshDashboard();
    }

    function bindEvents() {
        filterIds.forEach((id) => $(id).addEventListener("change", refreshDashboard));
        $("show-campaigns").addEventListener("change", () => {
            if (latestData) renderChart(latestData.series, latestData.campaigns, latestData.filters);
        });
        $("reset-filters").addEventListener("click", resetFilters);
    }

    async function init() {
        bindEvents();
        try {
            await loadOptions();
            // Default view is the latest complete fiscal year available in the database.
            $("start-date").value = "2025-07-01";
            $("end-date").value = latestOptions.max_date < "2026-06-30" ? latestOptions.max_date : "2026-06-30";
            await refreshDashboard();
        } catch (error) {
            $("chart-status").textContent = error.message;
            $("chart-status").classList.add("is-error");
        }
    }

    document.addEventListener("DOMContentLoaded", init);
})();
