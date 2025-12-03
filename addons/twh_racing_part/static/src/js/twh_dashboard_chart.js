/** @odoo-module **/

import { onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class TwhDashboardChart {
  setup() {
    this.rpc = useService("rpc");

    onMounted(() => {
      this.loadChart();
    });
  }

  async loadChart() {
    const result = await this.rpc("/twh/dashboard/chart", {});
    console.log("Chart data:", result);

    var options = {
      chart: {
        type: "line",
        height: 320,
      },
      series: [
        {
          name: "Total Penjualan",
          data: result.values,
        },
      ],
      xaxis: {
        categories: result.labels,
      },
    };

    let chart = new ApexCharts(
      document.querySelector("#sales_chart_root"),
      options
    );
    chart.render();
  }
}
