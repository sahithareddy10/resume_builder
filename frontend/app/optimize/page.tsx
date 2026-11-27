'use client';

import { useState, useLayoutEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, ArrowRight, Loader2, Target, CheckCircle2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Link from 'next/link';

interface ParsedResume {
 contact: { name: string; email?: string; phone?: string; linkedin?: string; github?: string; location?: string };
 summary?: string;
 experience: Array<{ title: string; company: string; description: string[] }>;
 education: Array<{ institution: string; degree: string; field_of_study: string }>;
 skills: Array<{ name: string; category: string }>;
 word_count: number;
 page_count: number;
}

const PROCESSING_STAGES = [
 { id: 'parsing', label: 'Parsing resume...' },
 { id: 'analyzing_jd', label: 'Analyzing job description...' },
 { id: 'extracting_evidence', label: 'Checking your experience...' },
 { id: 'optimizing', label: 'Optimizing resume...' },
 { id: 'safety_check', label: 'Running factual safety checks...' },
 { id: 'preparing_pdf', label: 'Preparing your PDF...' },
];

export default function OptimizePage() {
 const [resume, setResume] = useState<ParsedResume | null>(null);
 const [step, setStep] = useState<'form' | 'processing' | 'done'>('form');
 const [currentStage, setCurrentStage] = useState(0);
 const [result, setResult] = useState<any>(null);

 const [companyName, setCompanyName] = useState('');
 const [targetRole, setTargetRole] = useState('');
 const [jobDescription, setJobDescription] = useState('');
 const [selectedTemplate, setSelectedTemplate] = useState('professional');

 useLayoutEffect(() => {
 const stored = sessionStorage.getItem('resume_parsed');
 if (stored) {
 try {
 // Decode from base64 (upload page stores it as base64)
 const decoded = decodeURIComponent(escape(atob(stored)));
 setResume(JSON.parse(decoded));
 } catch {}
 }
}, []);

 const handleOptimize = async () => {
 if (!companyName || !targetRole || !jobDescription) {
 toast.error('Please fill in all fields');
 return;
 }
 if (!resume) {
 toast.error('No resume data found. Please upload first.');
 return;
 }

 setStep('processing');
 setCurrentStage(0);

 // Simulate processing stages for UX
 const stageInterval = setInterval(() => {
 setCurrentStage((prev) => {
 if (prev >= PROCESSING_STAGES.length - 1) {
 clearInterval(stageInterval);
 return prev;
 }
 return prev + 1;
 });
 }, 2000);

 try {
 const payload = {
 resume,
 company_name: companyName,
 target_role: targetRole,
 job_description: jobDescription,
 pdf_template: selectedTemplate,
 };

 const controller = new AbortController();
 const timer = window.setTimeout(() => controller.abort(), 600000);
 const res = await fetch('/api/resume/optimize', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify(payload),
 signal: controller.signal,
 });
 window.clearTimeout(timer);

 let data: any = null;
 try {
 data = await res.json();
 } catch {
 throw new Error('Optimization returned an invalid response. Is the backend running on port 8001?');
 }

 if (!res.ok || !data?.success) {
 const detail = data?.error || data?.detail || data?.safety?.issues?.[0];
 const message = typeof detail === 'string'
  ? detail
  : Array.isArray(detail)
  ? detail.map((item: any) => item?.msg || JSON.stringify(item)).join('; ')
  : 'Optimization failed';
 throw new Error(message);
 }

 setResult(data);
 setStep('done');
 setCurrentStage(PROCESSING_STAGES.length);
 toast.success('Resume optimized successfully!');
 } catch (err: any) {
 const message = err?.name === 'AbortError'
  ? 'Optimization timed out. Keep Ollama open and try again — the local model can take a few minutes.'
  : (err.message || 'Optimization failed');
 toast.error(message);
 setStep('form');
 } finally {
 clearInterval(stageInterval);
 }
 };

 if (step === 'processing') {
 return (
 <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
 <div className="text-center max-w-md mx-auto px-8">
 <Loader2 className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-6" />
 <h2 className="text-2xl font-bold text-white mb-6">Optimizing Your Resume</h2>
 <div className="space-y-3">
 {PROCESSING_STAGES.map((stage, idx) => (
 <div key={stage.id} className="flex items-center gap-3 text-left">
 <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 ${
 idx < currentStage ? 'border-green-500 bg-green-500/20' :
 idx === currentStage ? 'border-blue-500 bg-blue-500/20' :
 'border-slate-600'
 }`}>
 {idx < currentStage ? (
 <CheckCircle2 className="w-4 h-4 text-green-400" />
 ) : idx === currentStage ? (
 <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
 ) : null }
 </div>
 <span className={`text-sm ${idx <= currentStage ? 'text-white' : 'text-slate-500'}`}>
 {stage.label}
 </span>
 </div>
 ))}
 </div>
 <p className="text-slate-500 text-xs mt-8">The local LLM is rewriting your resume. Keep this tab open — the first run can take 2–4 minutes.</p>
 </div>
 </div>
 );
 }

 if (step === 'done' && result) {
 const rawScore = result?.analysis?.alignment_score;
 const score = typeof rawScore === 'object' && rawScore !== null
  ? Number(rawScore.overall || 0)
  : Number(rawScore || 0);
 const issues = result?.safety?.issues || [];
 const matched = result?.analysis?.matched_keywords || result?.analysis?.supported_skills || [];
 const engine = result?.analysis?.engine || 'enhancer';

 return (
 <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
 <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
 <Link href="/" className="flex items-center gap-2">
 <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
 <Target className="w-5 h-5 text-white" />
 </div>
 <span className="text-white font-bold text-xl">ResumeAI</span>
 </Link>
 <div className="flex gap-3">
 {result.pdf?.download_url && (
 <a
 href={result.pdf.download_url}
 target="_blank"
 rel="noopener noreferrer"
 className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg font-medium transition-all flex items-center gap-2"
 >
 Download PDF
 </a>
 )}
 </div>
 </nav>

 <main className="max-w-4xl mx-auto px-8 pt-8 pb-24">
 {/* Alignment Score */}
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-12">
 <div className={`inline-flex items-center justify-center w-28 h-28 rounded-full border-4 ${
 score >= 90 ? 'bg-green-500/10 border-green-500/30' :
 score >= 70 ? 'bg-yellow-500/10 border-yellow-500/30' :
 'bg-red-500/10 border-red-500/30'
 }`}>
 <span className={`text-4xl font-bold ${
 score >= 90 ? 'text-green-400' :
 score >= 70 ? 'text-yellow-400' :
 'text-red-400'
 }`}>
 {score}
 </span>
 </div>
 <h1 className="text-3xl font-bold text-white mb-2">ATS Match Score</h1>
 <p className="text-slate-400">How well your optimized resume matches this job description</p>
 <p className="text-slate-500 text-xs mt-2">Engine: {engine}</p>
 </motion.div>

 {/* Safety Status */}
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
 className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-8">
 <h2 className="text-white font-semibold text-lg mb-3">Safety Status</h2>
 <div className={`flex items-center gap-2 ${result?.safety?.passed ? 'text-green-400' : 'text-red-400'}`}>
 <CheckCircle2 className="w-5 h-5" />
 <span className="font-medium">{result?.safety?.passed ? 'Passed — no hallucinated facts' : 'Issues detected'}</span>
 </div>
 {issues.length > 0 && (
 <ul className="mt-2 space-y-1">
 {issues.map((issue: string, i: number) => (
 <li key={i} className="text-slate-400 text-sm">• {issue}</li>
 ))}
 </ul>
 )}
 </motion.div>

 {/* JD Keywords */}
 {matched.length > 0 && (
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}
 className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-8">
 <h2 className="text-white font-semibold text-lg mb-3">JD Keywords Added / Matched</h2>
 <div className="flex flex-wrap gap-2">
 {matched.slice(0, 24).map((skill: string) => (
 <span key={skill} className="bg-green-500/10 text-green-400 border border-green-500/20 px-3 py-1 rounded-lg text-sm">
 {skill}
 </span>
 ))}
 </div>
 </motion.div>
 )}

 {/* Supported Skills */}
 {result.analysis.supported_skills?.length > 0 && (
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
 className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-8">
 <h2 className="text-white font-semibold text-lg mb-3">Supported Skills</h2>
 <div className="flex flex-wrap gap-2">
 {result.analysis.supported_skills.slice(0, 15).map((skill: string) => (
 <span key={skill} className="bg-green-500/10 text-green-400 border border-green-500/20 px-3 py-1 rounded-lg text-sm">
 {skill}
 </span>
 ))}
 </div>
 </motion.div>
 )}

 {/* Optimized Resume Preview — FULL resume, no truncation */}
 {result.resume?.optimized_text && (
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
 className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-8">
 <h2 className="text-white font-semibold text-lg mb-4">Optimized Resume — Complete Preview</h2>
 <div className="bg-white text-black rounded-xl p-6 max-h-[700px] overflow-y-auto">
 <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed" style={{ fontFamily: 'Georgia, serif' }}>
 {result.resume.optimized_text}
 </pre>
 </div>
 </motion.div>
 )}

 <div className="text-center">
 <Link href="/" className="inline-block bg-slate-700 hover:bg-slate-600 text-white px-8 py-3 rounded-xl font-medium transition-all">
 Optimize Another Resume
 </Link>
 </div>
 </main>
 </div>
 );
 }

 return (
 <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
 <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
 <Link href="/" className="flex items-center gap-2">
 <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
 <Target className="w-5 h-5 text-white" />
 </div>
 <span className="text-white font-bold text-xl">ResumeAI</span>
 </Link>
 </nav>

 <main className="max-w-3xl mx-auto px-8 pt-12 pb-24">
 <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="mb-8">
 <h1 className="text-3xl font-bold text-white mb-2">Job Details</h1>
 <p className="text-slate-400">Tell us about the role you're targeting at {companyName || '...'}</p>
 </motion.div>

 <div className="space-y-6">
 <div>
 <label className="block text-white font-medium mb-2">Company Name *</label>
 <input
 type="text"
 value={companyName}
 onChange={(e) => setCompanyName(e.target.value)}
 placeholder="e.g., Google, Microsoft, Startup Inc."
 className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
 />
 </div>

 <div>
 <label className="block text-white font-medium mb-2">Target Role *</label>
 <input
 type="text"
 value={targetRole}
 onChange={(e) => setTargetRole(e.target.value)}
 placeholder="e.g., Senior Software Engineer"
 className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
 />
 </div>

 <div>
 <label className="block text-white font-medium mb-2">Job Description *</label>
 <textarea
 value={jobDescription}
 onChange={(e) => setJobDescription(e.target.value)}
 rows={14}
 placeholder="Paste the complete job description here..."
 className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors resize-y"
 />
 <p className="text-slate-500 text-sm mt-2">
 Include responsibilities, required skills, and qualifications for best results.
 </p>
 </div>

 <button
 onClick={handleOptimize}
 disabled={!companyName || !targetRole || !jobDescription}
 className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white py-4 rounded-xl font-semibold text-lg transition-all flex items-center justify-center gap-2"
 >
 <Target className="w-5 h-5" />
 Optimize Resume
 </button>
 </div>
 </main>
 </div>
 );
}
