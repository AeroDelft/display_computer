export function createGauge(id: string, min: number, max: number, zones: any) {
  const el = document.getElementById(id)!;
  const gauge: any = echarts.init(el);

  const getCurrentValue = (): number => {
    const opt = gauge.getOption?.();
    const maybe = opt?.series?.[0]?.data?.[0]?.value;
    return typeof maybe === "number" ? maybe : 0;
  };

  const applySizing = () => {
    const baseSize = Math.min(el.clientWidth || 200, el.clientHeight || 200);

    // These multipliers preserve the old "200px -> {24,12,8,3}" proportions.
    const detailFontSize = Math.max(10, Math.round(baseSize * 0.12));
    const axisLabelFontSize = Math.max(7, Math.round(baseSize * 0.06));
    const axisLineWidth = Math.max(4, Math.round(baseSize * 0.04));
    const pointerWidth = Math.max(2, Math.round(baseSize * 0.015));

    gauge.setOption(
      {
        series: [
          {
            type: "gauge",
            startAngle: 225,
            endAngle: -45,
            min,
            max,
            splitNumber: 4,
            animationDurationUpdate: 40,
            axisLine: {
              lineStyle: {
                width: axisLineWidth,
                color: zones,
              },
            },
            pointer: {
              length: "75%",
              width: pointerWidth,
            },
            detail: {
              formatter: "{value}",
              color: "white",
              fontSize: detailFontSize,
              offsetCenter: [0, "65%"],
            },
            axisLabel: {
              color: "white",
              fontSize: axisLabelFontSize,
            },
            data: [{ value: getCurrentValue() }],
          },
        ],
      },
      true
    );

    gauge.resize();
  };

  // Initial sizing (and again after layout settles via ResizeObserver)
  applySizing();

  // Keep gauge typography proportional to CSS-clamped gauge size.
  const ro = new ResizeObserver(() => applySizing());
  ro.observe(el);

  return gauge;
}