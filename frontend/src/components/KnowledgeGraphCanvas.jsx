import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

function KnowledgeGraphCanvas({ data }) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!svgRef.current || !data?.nodes?.length) return

    const width = 900
    const height = 520

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    svg.attr('viewBox', `0 0 ${width} ${height}`)

    const container = svg.append('g')

    svg.call(
      d3
        .zoom()
        .scaleExtent([0.4, 2.5])
        .on('zoom', (event) => {
          container.attr('transform', event.transform)
        }),
    )

    const link = container
      .append('g')
      .selectAll('line')
      .data(data.edges || [])
      .join('line')
      .attr('stroke', 'rgba(148,163,184,0.55)')
      .attr('stroke-width', 1.2)

    const node = container
      .append('g')
      .selectAll('circle')
      .data(data.nodes)
      .join('circle')
      .attr('r', 10)
      .attr('fill', '#6366f1')
      .attr('stroke', '#c7d2fe')
      .attr('stroke-width', 1.2)
      .call(
        d3
          .drag()
          .on('start', dragStarted)
          .on('drag', dragged)
          .on('end', dragEnded),
      )

    const labels = container
      .append('g')
      .selectAll('text')
      .data(data.nodes)
      .join('text')
      .text((d) => d.label || d.id || 'concept')
      .attr('font-size', 11)
      .attr('fill', '#e2e8f0')
      .attr('dx', 14)
      .attr('dy', 4)

    node.append('title').text((d) => d.label || d.id)

    const simulation = d3
      .forceSimulation(data.nodes)
      .force(
        'link',
        d3
          .forceLink(data.edges || [])
          .id((d) => d.id)
          .distance(90),
      )
      .force('charge', d3.forceManyBody().strength(-230))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .on('tick', ticked)

    function ticked() {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)

      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y)
      labels.attr('x', (d) => d.x).attr('y', (d) => d.y)
    }

    function dragStarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      event.subject.fx = event.subject.x
      event.subject.fy = event.subject.y
    }

    function dragged(event) {
      event.subject.fx = event.x
      event.subject.fy = event.y
    }

    function dragEnded(event) {
      if (!event.active) simulation.alphaTarget(0)
      event.subject.fx = null
      event.subject.fy = null
    }

    return () => simulation.stop()
  }, [data])

  return <svg ref={svgRef} className="h-[520px] w-full rounded-xl border border-slate-700/70 bg-slate-950/40" />
}

export default KnowledgeGraphCanvas
