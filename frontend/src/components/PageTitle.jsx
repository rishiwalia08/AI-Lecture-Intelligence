import { motion } from 'framer-motion'

function PageTitle({ title, subtitle }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mb-5"
    >
      <h1 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">{title}</h1>
      {subtitle ? <p className="mt-1 text-sm text-slate-300">{subtitle}</p> : null}
    </motion.div>
  )
}

export default PageTitle
