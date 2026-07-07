"use client"

import React, { type ReactNode } from "react"
import { motion } from "framer-motion"

interface PageTransitionProps {
  children: ReactNode
  className?: string
}

const pageVariants: any = {
  initial: {
    opacity: 0,
    y: 16,
    scale: 0.99,
  },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.35,
      ease: [0.25, 0.46, 0.45, 0.94],
    },
  },
  exit: {
    opacity: 0,
    y: -8,
    scale: 0.99,
    transition: {
      duration: 0.2,
    },
  },
}

export default function PageTransition({ children, className }: PageTransitionProps) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className={className}
    >
      {children}
    </motion.div>
  )
}
