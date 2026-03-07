import { motion } from 'framer-motion'

function KpiCard({ label, value, icon = '📊' }) {
  return (
    <motion.div
      whileHover={{ y: -2, scale: 1.01 }}
      className="glass rounded-2xl p-4"
    >
      <p className="text-xs text-slate-300">{icon} {label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </motion.div>
  )
}

export default KpiCard
