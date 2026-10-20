(() => {
    const $ = (id) => document.getElementById(id);
    const filterIds = ["search", "start-date", "end-date", "academic-unit", "campaign", "gift-type", "status", "page-size"];
    const state = { page: 1, sort: "gift_date", direction: "desc", total: 0, pages: 1, loading: false };
    let options = null;
    let searchTimer = null;

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (character) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
        })[character]);
    }

    function money(cents) {
        return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(Number(cents || 0) / 100);
    }

    function queryParams(includePage = true) {
        const params = new URLSearchParams();
        params.set("search", $("search").value.trim());
        params.set("start_date", $("start-date").value);
        params.set("end_date", $("end-date").value);
        params.set("academic_unit", $("academic-unit").value);
        params.set("campaign", $("campaign").value);
        params.set("gift_type", $("gift-type").value);
        params.set("status", $("status").value);
        params.set("sort", state.sort);
        params.set("direction", state.direction);
        if (includePage) {
            params.set("page", String(state.page));
            params.set("page_size", $("page-size").value);
        }
        return params;
    }

    async function loadOptions() {
        const response = await fetch("/api/data/options");
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load filter options.");
        options = data;
        data.academic_units.forEach((unit) => {
            const option = document.createElement("option");
            option.value = unit.id;
            option.textContent = unit.name;
            $("academic-unit").append(option);
        });
        data.campaigns.forEach((campaign) => {
            const option = document.createElement("option");
            option.value = campaign.id;
            option.textContent = campaign.name;
            $("campaign").append(option);
        });
        $("start-date").min = data.min_date;
        $("start-date").max = data.max_date;
        $("end-date").min = data.min_date;
        $("end-date").max = data.max_date;
        $("start-date").value = data.min_date;
        $("end-date").value = data.max_date;
    }

    async function loadData() {
        if (state.loading) return;
        state.loading = true;
        $("filter-status").textContent = "Loading records…";
        try {
            const response = await fetch(`/api/data?${queryParams().toString()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Could not load records.");
            state.total = data.total;
            state.page = data.page;
            state.pages = data.pages;
            renderRows(data.rows);
            renderPagination(data);
            renderSortHeaders();
            $("result-count").textContent = `${data.total.toLocaleString("en-US")} transaction${data.total === 1 ? "" : "s"} match the current filters`;
            $("filter-status").textContent = "Filters apply to every matching record, including CSV export.";
        } catch (error) {
            $("data-table-body").innerHTML = `<tr><td class="empty-cell" colspan="10">${escapeHtml(error.message)}</td></tr>`;
            $("filter-status").textContent = error.message;
            $("result-count").textContent = "Records could not be loaded";
        } finally {
            state.loading = false;
        }
    }

    function renderRows(rows) {
        const tbody = $("data-table-body");
        if (!rows.length) {
            tbody.innerHTML = '<tr><td class="empty-cell" colspan="10">No transactions match these filters. Try changing or resetting the filters.</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map((row) => `<tr>
            <td>${escapeHtml(row.gift_id)}</td>
            <td>${escapeHtml(row.gift_date)}</td>
            <td>${escapeHtml(row.donor_name)}</td>
            <td>${escapeHtml(row.graduation_year)}</td>
            <td>${escapeHtml(row.unit_name)}</td>
            <td>${escapeHtml(row.campaign_name || "—")}</td>
            <td class="amount-cell">${money(row.amount_cents)}</td>
            <td>${escapeHtml(formatLabel(row.gift_type))}</td>
            <td><span class="status-tag status-tag--${escapeHtml(row.status)}">${escapeHtml(formatLabel(row.status))}</span></td>
            <td class="note-cell" title="${escapeHtml(row.note)}">${escapeHtml(row.note || "—")}</td>
        </tr>`).join("");
    }

    function formatLabel(value) {
        return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function renderPagination(data) {
        const start = data.total ? ((data.page - 1) * data.page_size) + 1 : 0;
        const end = Math.min(data.page * data.page_size, data.total);
        $("page-summary").textContent = `Showing ${start}–${end} of ${data.total.toLocaleString("en-US")} · Page ${data.page} of ${data.pages}`;
        $("first-page").disabled = data.page <= 1;
        $("previous-page").disabled = data.page <= 1;
        $("next-page").disabled = data.page >= data.pages;
        $("last-page").disabled = data.page >= data.pages;
    }

    function renderSortHeaders() {
        document.querySelectorAll(".sort-button").forEach((button) => {
            const active = button.dataset.sort === state.sort;
            button.classList.toggle("is-sorted", active);
            button.querySelector("span").textContent = active ? (state.direction === "asc" ? "↑" : "↓") : "";
            button.setAttribute("aria-sort", active ? (state.direction === "asc" ? "ascending" : "descending") : "none");
        });
    }

    function resetFilters() {
        if (!options) return;
        $("search").value = "";
        $("start-date").value = options.min_date;
        $("end-date").value = options.max_date;
        $("academic-unit").value = "all";
        $("campaign").value = "all";
        $("gift-type").value = "all";
        $("status").value = "all";
        $("page-size").value = "50";
        state.sort = "gift_date";
        state.direction = "desc";
        state.page = 1;
        loadData();
    }

    function exportCsv() {
        const params = queryParams(false);
        window.location.href = `/api/data/export.csv?${params.toString()}`;
    }

    function scheduleSearch() {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.page = 1;
            loadData();
        }, 250);
    }

    filterIds.forEach((id) => {
        if ($(id).tagName === "SELECT") {
            $(id).addEventListener("change", () => {
                state.page = 1;
                loadData();
            });
        } else {
            $(id).addEventListener("input", () => {
                state.page = 1;
                if (id === "search") scheduleSearch();
                else loadData();
            });
        }
    });

    document.querySelectorAll(".sort-button").forEach((button) => {
        button.addEventListener("click", () => {
            if (state.sort === button.dataset.sort) {
                state.direction = state.direction === "asc" ? "desc" : "asc";
            } else {
                state.sort = button.dataset.sort;
                state.direction = state.sort === "gift_date" || state.sort === "gift_id" ? "desc" : "asc";
            }
            state.page = 1;
            loadData();
        });
    });

    $("first-page").addEventListener("click", () => { state.page = 1; loadData(); });
    $("previous-page").addEventListener("click", () => { state.page = Math.max(1, state.page - 1); loadData(); });
    $("next-page").addEventListener("click", () => { state.page = Math.min(state.pages, state.page + 1); loadData(); });
    $("last-page").addEventListener("click", () => { state.page = state.pages; loadData(); });
    $("reset-filters").addEventListener("click", resetFilters);
    $("export-csv").addEventListener("click", exportCsv);

    loadOptions().then(loadData).catch((error) => {
        $("filter-status").textContent = error.message;
        $("result-count").textContent = "Could not initialize data table";
        $("data-table-body").innerHTML = `<tr><td class="empty-cell" colspan="10">${escapeHtml(error.message)}</td></tr>`;
    });
})();
