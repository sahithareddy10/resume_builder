'use client';

import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Upload, FileText, Shield, Zap, ChevronRight } from 'lucide-react';
import Link from 'next/link';

export default function HomePage() {
 return (
 <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
 <div className="absolute inset-0 overflow-hidden">
 <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl" />
 <div className="absolute top-1/2 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl" />
 </div>

 <div className="relative">
 <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
 <div className="flex items-center gap-2">
 <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
 <FileText className="w-5 h-5 text-white" />
 </div>
 <span className="text-white font-bold text-xl">ResumeAI</span>
 </div>
 <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
 <span className="hover:text-white transition-colors">Features</span>
 <span className="hover:text-white transition-colors">How It Works</span>
 <Link href="/upload" className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg font-medium transition-all">
 Get Started
 </Link>
 </div>
 </nav>

 <main className="max-w-7xl mx-auto px-8 pt-20 pb-32">
 <motion.div
 initial={{ opacity: 0, y: 20 }}
 animate={{ opacity: 1, y: 0 }}
 transition={{ duration: 0.6 }}
 className="text-center max-w-3xl mx-auto"
 >
 <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 text-blue-400 px-4 py-1.5 rounded-full text-sm mb-8">
 <Zap className="w-4 h-4" />
 AI-Powered Resume Optimization
 </div>

 <h1 className="text-5xl md:text-7xl font-bold text-white leading-tight mb-6">
 Optimize Your Resume.
 <br />
 <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
 For Any Role.
 </span>
 </h1>

 <p className="text-lg md:text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
 Upload your resume, add a job description, and get an
 optimized version tailored to that exact role — with
 factual accuracy guaranteed.
 </p>

 <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
 <Link
 href="/upload"
 className="group bg-blue-600 hover:bg-blue-500 text-white px-8 py-4 rounded-xl font-semibold text-lg transition-all hover:shadow-xl hover:shadow-blue-500/25 flex items-center gap-2"
 >
 <Upload className="w-5 h-5" />
 Upload Your Resume
 <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
 </Link>
 </div>
 </motion.div>

 <motion.div
 initial={{ opacity: 0, y: 30 }}
 animate={{ opacity: 1, y: 0 }}
 transition={{ duration: 0.6, delay: 0.3 }}
 className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-24"
 >
 {[
 { icon: Shield, label: 'Factual Accuracy', desc: 'Never invents experience, skills, or achievements' },
 { icon: Zap, label: 'Role-Aligned', desc: 'Optimized for any role — tech, finance, marketing, HR, and more' },
 { icon: FileText, label: 'PDF Export', desc: 'Clean, professional, one-page resume PDF' },
 ].map((stat) => (
 <div key={stat.label} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-8 text-center">
 <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mx-auto mb-4">
 <stat.icon className="w-6 h-6 text-blue-400" />
 </div>
 <h3 className="text-white font-semibold text-lg mb-2">{stat.label}</h3>
 <p className="text-slate-400 text-sm">{stat.desc}</p>
 </div>
 ))}
 </motion.div>

 <section className="mt-32">
 <motion.div
 initial={{ opacity: 0 }}
 whileInView={{ opacity: 1 }}
 viewport={{ once: true }}
 className="text-center mb-16"
 >
 <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">How It Works</h2>
 <p className="text-slate-400 max-w-xl mx-auto">Three simple steps to a perfectly optimized resume</p>
 </motion.div>

 <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
 {[
 { step: '1', title: 'Upload Resume', desc: 'Upload your resume as PDF, DOCX, or TXT.' },
 { step: '2', title: 'Add Job Details', desc: 'Paste the job description, company name, and target role.' },
 { step: '3', title: 'Get Optimized Resume', desc: 'AI rewrites your resume with factual accuracy, safety checks, and PDF export.' },
 ].map((item) => (
 <motion.div
 key={item.step}
 initial={{ opacity: 0, y: 20 }}
 whileInView={{ opacity: 1, y: 0 }}
 viewport={{ once: true }}
 transition={{ delay: parseInt(item.step) * 0.15 }}
 >
 <div className="bg-slate-800/30 border border-slate-700/50 rounded-2xl p-8">
 <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center text-white font-bold text-lg mb-6">
 {item.step}
 </div>
 <h3 className="text-white font-semibold text-xl mb-3">{item.title}</h3>
 <p className="text-slate-400 leading-relaxed">{item.desc}</p>
 </div>
 </motion.div>
 ))}
 </div>
 </section>
 </main>

 <footer className="border-t border-slate-800 mt-20">
 <div className="max-w-7xl mx-auto px-8 py-8 text-center">
 <p className="text-slate-500 text-sm">AI Resume Optimizer — Built with Next.js + FastAPI + </p>
 </div>
 </footer>
 </div>
 </div>
 );
}
