/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TwhDashboard extends Component {
  static template = "twh_racing_part.Dashboard";
  static props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    className: { type: String, optional: true },
  };

  setup() {
    this.orm = useService("orm");
    this.rpc = useService("rpc");
    this.state = useState({
      total_products: 0,
      total_customers: 0,
      unpaid_invoices: 0,
      total_revenue: "Rp 0",
      revenue_period: "month", // Default: This Month
      revenue_period_label: "This Month",
      revenue_invoice_count: 0,
      monthly_sales: [],
    });

    onMounted(() => {
      this.loadDashboardData();
    });
  }

  async loadDashboardData(revenuePeriod = "month") {
    try {
      // Hitung total products
      this.state.total_products = await this.orm.searchCount(
        "product.product",
        [["sale_ok", "=", true]]
      );

      // Hitung total customers (hanya yang aktif)
      this.state.total_customers = await this.orm.searchCount("res.partner", [
        ["customer_rank", ">", 0],
        ["active", "=", true],
      ]);

      // Hitung unpaid invoices dari twh.invoice (confirmed tapi belum paid)
      this.state.unpaid_invoices = await this.orm.searchCount("twh.invoice", [
        ["state", "=", "confirmed"],
      ]);

      // Get Revenue Data with Period Filter
      const revenueData = await this.orm.call(
        "twh.dashboard",
        "get_total_revenue",
        [revenuePeriod]
      );

      this.state.total_revenue = revenueData.formatted || "Rp 0";
      this.state.revenue_period = revenueData.period || "month";
      this.state.revenue_period_label =
        revenueData.period_label || "This Month";
      this.state.revenue_invoice_count = revenueData.invoice_count || 0;

      // Ambil data penjualan REAL dari RPC
      const salesData = await this.rpc("/twh/dashboard/sales_data", {});
      this.state.monthly_sales = salesData || [];

      // Render chart setelah DOM ready
      setTimeout(() => this.renderCharts(), 100);

      console.log("✅ Dashboard loaded:", {
        revenue: this.state.total_revenue,
        period: this.state.revenue_period_label,
        invoices: this.state.revenue_invoice_count,
      });
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
    }
  }

  // NEW: Handle Revenue Period Change
  async onRevenuePeriodChange(event) {
    const newPeriod = event.target.value;
    console.log("📅 Changing revenue period to:", newPeriod);

    // Reload hanya revenue data
    try {
      const revenueData = await this.orm.call(
        "twh.dashboard",
        "get_total_revenue",
        [newPeriod]
      );

      this.state.total_revenue = revenueData.formatted || "Rp 0";
      this.state.revenue_period = revenueData.period || "month";
      this.state.revenue_period_label =
        revenueData.period_label || "This Month";
      this.state.revenue_invoice_count = revenueData.invoice_count || 0;

      console.log("✅ Revenue updated:", {
        period: this.state.revenue_period_label,
        amount: this.state.total_revenue,
        invoices: this.state.revenue_invoice_count,
      });
    } catch (error) {
      console.error("Failed to update revenue:", error);
    }
  }

  renderCharts() {
    if (typeof ApexCharts === "undefined") {
      console.error("ApexCharts library not loaded");
      return;
    }

    const chartElement = document.querySelector("#monthly_sales");
    if (!chartElement) {
      console.error("Chart element #monthly_sales not found");
      return;
    }

    // Clear existing chart
    chartElement.innerHTML = "";

    const options = {
      series: [
        {
          name: "Total Penjualan (Rp)",
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

    const chart = new ApexCharts(chartElement, options);
    chart.render();
  }

  // Method untuk refresh data
  async refreshDashboard() {
    await this.loadDashboardData(this.state.revenue_period);
  }
}

registry.category("actions").add("twh_dashboard", TwhDashboard);
