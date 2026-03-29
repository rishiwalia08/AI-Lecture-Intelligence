import { motion } from 'framer-motion'
import { VerticalTimeline, VerticalTimelineElement } from 'react-vertical-timeline-component'
import 'react-vertical-timeline-component/style.min.css'
import PageTitle from '../components/PageTitle'

const timelineData = [
  { time: '00:00', title: 'Lecture Start', description: 'Upload or ingest a lecture to generate real timeline topics.' },
  { time: '08:00', title: 'Topic Segment', description: 'Detected topics will appear with timestamps after ingestion.' },
  { time: '16:00', title: 'Examples', description: 'Ask questions in chat to jump to relevant moments in the video.' },
  { time: '24:00', title: 'Summary', description: 'Use the summaries page for concise lecture notes.' },
]

function TimelinePage() {
  return (
    <section>
      <PageTitle title="Lecture Timeline" subtitle="Interactive topic map across lecture time." />
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-2xl border border-slate-700/70 bg-slate-900/30 p-4">
        <VerticalTimeline lineColor="rgba(99, 102, 241, 0.6)">
          {timelineData.map((item) => (
            <VerticalTimelineElement
              key={`${item.time}-${item.title}`}
              date={item.time}
              contentStyle={{
                background: 'rgba(30,41,59,0.7)',
                color: '#e2e8f0',
                border: '1px solid rgba(148,163,184,0.3)',
                borderRadius: '16px',
                boxShadow: 'none',
              }}
              contentArrowStyle={{ borderRight: '7px solid rgba(99,102,241,0.8)' }}
              iconStyle={{ background: '#6366f1', color: '#fff', boxShadow: '0 0 0 4px rgba(99,102,241,0.3)' }}
              icon={<span className="text-xs">•</span>}
            >
              <h3 className="text-base font-semibold">{item.title}</h3>
              <p className="mt-1 text-sm text-slate-300">{item.description}</p>
            </VerticalTimelineElement>
          ))}
        </VerticalTimeline>
      </motion.div>
    </section>
  )
}

export default TimelinePage
