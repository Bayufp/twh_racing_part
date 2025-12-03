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
    this.state = useState({
      total_products: 0,
      total_customers: 0,
      pending_invoices: 0,
      monthly_sales: [],
    });

    onMounted(() => {
      this.loadDashboardData();
    });
  }

  async loadDashboardData() {
    try {
      // Hitung total products
      this.state.total_products = await this.orm.searchCount(
        "product.product",
        []
      );

      // Hitung total customers
      this.state.total_customers = await this.orm.searchCount("res.partner", [
        ["customer_rank", ">", 0],
      ]);

      // Hitung pending invoices
      this.state.pending_invoices = await this.orm.searchCount("account.move", [
        ["move_type", "=", "out_invoice"],
        ["payment_state", "=", "not_paid"],
      ]);

      // Data sales dummy
      this.state.monthly_sales = [
        { month: "Jan", amount: 15000 },
        { month: "Feb", amount: 23000 },
        { month: "Mar", amount: 18000 },
        { month: "Apr", amount: 32000 },
        { month: "May", amount: 28000 },
        { month: "Jun", amount: 35000 },
      ];

      this.renderCharts();
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
    }
  }

  renderCharts() {
    if (typeof ApexCharts === "undefined") {
      console.error("ApexCharts not loaded");
      return;
    }

    const chartElement = document.querySelector("#monthly_sales");
    if (!chartElement) {
      console.error("Chart element not found");
      return;
    }

    const options = {
      series: [
        {
          name: "Sales",
          data: this.state.monthly_sales.map((item) => item.amount),
        },
      ],
      chart: {
        type: "line",
        height: 350,
      },
      xaxis: {
        categories: this.state.monthly_sales.map((item) => item.month),
      },
      stroke: {
        curve: "smooth",
      },
      colors: ["#7E3AF2"],
    };

    const chart = new ApexCharts(chartElement, options);
    chart.render();
  }
}

registry.category("actions").add("twh_dashboard", TwhDashboard);
