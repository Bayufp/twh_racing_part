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
      total_outstanding: "Rp 0",
      overdue_count: 0,
      partial_count: 0,
      total_revenue: "Rp 0",
      revenue_period: "month",
      revenue_period_label: "This Month",
      revenue_payment_count: 0,
      revenue_invoice_count: 0,
      monthly_sales: [],
    });

    onMounted(() => {
      this.loadDashboardData();
    });
  }

  async loadDashboardData(revenuePeriod = "month") {
    try {
      // Call dashboard summary dengan revenue period
      const summary = await this.orm.call(
        "twh.dashboard",
        "get_dashboard_summary",
        [revenuePeriod]
      );

      // Update state dengan data dari backend
      this.state.total_products = summary.total_products || 0;
      this.state.total_customers = summary.total_customers || 0;
      this.state.unpaid_invoices = summary.unpaid_invoices || 0;
      this.state.total_outstanding = summary.total_outstanding || "Rp 0";
      this.state.overdue_count = summary.overdue_count || 0;
      this.state.partial_count = summary.partial_count || 0;
      this.state.total_revenue = summary.total_revenue || "Rp 0";
      this.state.revenue_period = summary.revenue_period || "month";
      this.state.revenue_period_label =
        summary.revenue_period_label || "This Month";
      this.state.revenue_payment_count = summary.revenue_payment_count || 0;
      this.state.revenue_invoice_count = summary.revenue_invoice_count || 0;
      this.state.monthly_sales = summary.monthly_sales || [];

      // Render chart setelah DOM ready
      setTimeout(() => this.renderCharts(), 100);

      console.log("✅ Dashboard loaded:", {
        revenue: this.state.total_revenue,
        period: this.state.revenue_period_label,
        payments: this.state.revenue_payment_count,
        invoices: this.state.revenue_invoice_count,
        unpaid: this.state.unpaid_invoices,
        outstanding: this.state.total_outstanding,
      });
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
    }
  }

  // Handle Revenue Period Change
  async onRevenuePeriodChange(event) {
    const newPeriod = event.target.value;
    console.log("📅 Changing revenue period to:", newPeriod);
    await this.loadDashboardData(newPeriod);
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
          name: "Total Sales (Invoices Created)", // ← CHANGED
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
