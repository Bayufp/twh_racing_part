/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Component Dashboard TWH Racing Part
 *
 * Component ini menampilkan dashboard dengan:
 * - Statistik summary (produk, customer, piutang, revenue)
 * - Grafik penjualan bulanan (6 bulan terakhir)
 * - Filter periode untuk revenue
 */
export class TwhDashboard extends Component {
  static template = "twh_racing_part.Dashboard";
  static props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    className: { type: String, optional: true },
  };

  setup() {
    // Setup services
    this.orm = useService("orm");
    this.rpc = useService("rpc");

    // State management
    this.state = useState({
      // Summary Statistics
      total_products: 0,
      total_customers: 0,
      unpaid_invoices: 0,
      total_outstanding: "Rp 0",
      overdue_count: 0,
      partial_count: 0,

      // Revenue Data
      total_revenue: "Rp 0",
      revenue_period: "month",
      revenue_period_label: "Bulan Ini",
      revenue_payment_count: 0,
      revenue_invoice_count: 0,

      // Sales Chart Data
      monthly_sales: [],
    });

    // Load data saat component mounted
    onMounted(() => {
      this.loadDashboardData();
    });
  }

  /**
   * Load semua data dashboard dari backend
   *
   * @param {string} revenuePeriod - Periode revenue ('month', 'year', 'all')
   */
  async loadDashboardData(revenuePeriod = "month") {
    try {
      // Panggil method backend untuk ambil summary
      const summary = await this.orm.call(
        "twh.dashboard",
        "get_dashboard_summary",
        [revenuePeriod]
      );

      // Update state dengan data dari backend
      this.updateStateFromSummary(summary);

      // Render chart setelah DOM ready
      setTimeout(() => this.renderSalesChart(), 100);

      console.log("Dashboard berhasil dimuat:", {
        revenue: this.state.total_revenue,
        period: this.state.revenue_period_label,
        unpaid: this.state.unpaid_invoices,
      });
    } catch (error) {
      console.error("Gagal memuat data dashboard:", error);
    }
  }

  /**
   * Update state component dari data summary backend
   *
   * @param {Object} summary - Data summary dari backend
   */
  updateStateFromSummary(summary) {
    this.state.total_products = summary.total_products || 0;
    this.state.total_customers = summary.total_customers || 0;
    this.state.unpaid_invoices = summary.unpaid_invoices || 0;
    this.state.total_outstanding = summary.total_outstanding || "Rp 0";
    this.state.overdue_count = summary.overdue_count || 0;
    this.state.partial_count = summary.partial_count || 0;
    this.state.total_revenue = summary.total_revenue || "Rp 0";
    this.state.revenue_period = summary.revenue_period || "month";
    this.state.revenue_period_label =
      summary.revenue_period_label || "Bulan Ini";
    this.state.revenue_payment_count = summary.revenue_payment_count || 0;
    this.state.revenue_invoice_count = summary.revenue_invoice_count || 0;
    this.state.monthly_sales = summary.monthly_sales || [];
  }

  /**
   * Handler untuk perubahan periode revenue
   *
   * @param {Event} event - Change event dari dropdown
   */
  async onRevenuePeriodChange(event) {
    const newPeriod = event.target.value;
    console.log("Mengubah periode revenue ke:", newPeriod);
    await this.loadDashboardData(newPeriod);
  }

  /**
   * Render grafik penjualan menggunakan ApexCharts
   */
  renderSalesChart() {
    // Validasi library ApexCharts sudah loaded
    if (typeof ApexCharts === "undefined") {
      console.error("Library ApexCharts belum dimuat");
      return;
    }

    // Ambil element chart
    const chartElement = document.querySelector("#monthly_sales");
    if (!chartElement) {
      console.error("Element chart #monthly_sales tidak ditemukan");
      return;
    }

    // Clear chart yang sudah ada
    chartElement.innerHTML = "";

    // Konfigurasi chart
    const options = this.getChartOptions();

    // Render chart
    const chart = new ApexCharts(chartElement, options);
    chart.render();
  }

  /**
   * Get konfigurasi chart ApexCharts
   *
   * @returns {Object} - Konfigurasi chart
   */
  getChartOptions() {
    return {
      series: [
        {
          name: "Total Penjualan (Invoice Dibuat)",
          data: this.state.monthly_sales.map((item) => item.amount),
        },
      ],
      chart: {
        type: "area",
        height: 350,
        toolbar: {
          show: true,
        },
        zoom: {
          enabled: false,
        },
      },
      dataLabels: {
        enabled: false,
      },
      stroke: {
        curve: "smooth",
        width: 3,
      },
      colors: ["#7E3AF2"],
      fill: {
        type: "gradient",
        gradient: {
          shadeIntensity: 1,
          opacityFrom: 0.7,
          opacityTo: 0.2,
          stops: [0, 90, 100],
        },
      },
      xaxis: {
        categories: this.state.monthly_sales.map((item) => item.month),
        labels: {
          style: {
            fontSize: "12px",
          },
        },
      },
      yaxis: {
        labels: {
          formatter: function (value) {
            return "Rp " + value.toLocaleString("id-ID");
          },
        },
      },
      tooltip: {
        y: {
          formatter: function (value) {
            return "Rp " + value.toLocaleString("id-ID");
          },
        },
      },
      grid: {
        borderColor: "#f1f1f1",
      },
    };
  }

  /**
   * Method untuk refresh dashboard
   * Dipanggil saat user klik button Refresh
   */
  async refreshDashboard() {
    await this.loadDashboardData(this.state.revenue_period);
  }
}

// Register component ke Odoo registry
registry.category("actions").add("twh_dashboard", TwhDashboard);
