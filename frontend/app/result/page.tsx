'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
 ArrowLeft, Download, CheckCircle2, AlertCircle, TrendingUp,
 Shield, FileText, Loader2, ChevronDown, ChevronUp, Sparkles, Target
} from 'lucide-react';
import toast from 'react-hot-toast';
import Link from 'next/link';

interface ATSScore {
 overall: number;
 keyword_match: number;
 formatting_score: number;
 structure_score: number;
 missing_keywords: string[];
 matched_keywords: string[];
 issues: string[];
}

interface Suggestion {
 category: string;
 severity: string;
 original?: string;
 suggested: string;
 reason: string;
 ats_impact: number;
}

interface SectionOpt {
 section: string;
 suggestions: Suggestion[];
 optimized_content?: Record<string, any>;
}

interface OptResponse {
 task_id: string;
 status: string;
 ats_scores?: ATSScore;
 section_optimizations: SectionOpt[];
 overall_improvement?: number;
 optimized_resume?: any;
}

export default function ResultPage() {
 const [data, setData] = useState<OptResponse | null>(null);
 const [loading, setLoading] = useState(true);
 const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
 const [generatingPDF, setGeneratingPDF] = useState(false);

 useEffect(() => {
 const params = new URLSearchParams(window.location.search);
 const tid = params.get('taskId');
 if (!tid) return;

 // Poll for completion
 const interval = setInterval(async () => {
 try {
 const res = await fetch(`/api/v1/status/${tid}`);
 const d = await res.json();
 if (d.status === 'completed') {
 setData(d);
 setLoading(false);
 clearInterval(interval);
 }
 } catch {
 // retry
 }
 }, 2000);

 return () => clearInterval(interval);
 }, []);

 const toggleSection = (section: string) => {
 setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
 };

 const getScoreColor = (score: number) => {
 if (score >= 80) return 'text-green-400';
 if (score >= 60) return 'text-yellow-400';
 return 'text-red-400';
 };

 const getScoreBg = (score: number) => {
 if (score >= 80) return 'bg-green-500/10 border-green-500/30';
 if (score >= 60) return 'bg-yellow-500/10 border-yellow-500/30';
 return 'bg-red-500/10 border-red-500/30';
 };

 const handleDownloadPDF = async () => {
 if (!data?.optimized_resume || !data?.ats_scores) return;
 setGeneratingPDF(true);
 try {
 const res = await fetch('/api/v1/pdf/generate', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({
 resume: data.optimized_resume,
 template: 'modern',
 include_ats_score: true,
 }),
 });
 const result = await res.json();
 if (result.download_url) {
 window.open(result.download_url, '_blank');
 toast.success('PDF downloaded!');
 }
 } catch {
 toast.error('PDF generation failed');
 } finally {
 setGeneratingPDF(false);
 }
 };

 if (loading) {
 return (
 <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
 <div className="text-center">
 <motion.div
 animate={{ rotate: 360 }}
 transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
 className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full mx-auto mb-6"
 />
 <h2 className="text-2xl font-bold text-white mb-2">Optimizing Your Resume</h2>
 <p className="text-slate-400">AI is analyzing and rewriting your resume...</p>
 <p className="text-slate-500 text-sm mt-2">This may take 30-60 seconds depending on your hardware</p>
 </div>
 </div>
 );
 }

 if (!data?.ats_scores) return null;

 const ats = data.ats_scores;
 const improvement = data.overall_improvement || 0;

 return (
 <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
 <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
 <Link href="/" className="flex items-center gap-2">
 <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
 <Sparkles className="w-5 h-5 text-white" />
 </div>
 <span className="text-white font-bold text-xl">ResumeAI</span>
 </Link>
 <button
 onClick={handleDownloadPDF}
 disabled={generatingPDF}
 className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white px-6 py-2.5 rounded-lg font-medium transition-all flex items-center gap-2"
 >
 {generatingPDF ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
 {generatingPDF ? 'Generating...' : 'Download PDF'}
 </button>
 </nav>

 <main className="max-w-5xl mx-auto px-8 pt-8 pb-24">
 {/* Score Overview */}
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-12">
 <div className={`inline-flex items-center justify-center w-32 h-32 rounded-full border-4 ${getScoreBg(ats.overall)} mb-4`}>
 <span className={`text-4xl font-bold ${getScoreColor(ats.overall)}`}>{ats.overall}</span>
 </div>
 <h1 className="text-3xl font-bold text-white mb-2">ATS Compatibility Score</h1>
 {improvement > 0 ? (
 <p className="text-green-400 flex items-center justify-center gap-1">
 <TrendingUp className="w-5 h-5" /> +{improvement} points improvement
 </p>
 ) : (
 <p className="text-slate-400">Analysis complete</p>
 )}
 </motion.div>

 {/* Score Breakdown */}
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
 {[
 { label: 'Keywords', score: ats.keyword_match, icon: Target },
 { label: 'Formatting', score: ats.formatting_score, icon: FileText },
 { label: 'Structure', score: ats.structure_score, icon: Shield },
 { label: 'Overall', score: ats.overall, icon: CheckCircle2 },
 ].map((item) => (
 <div key={item.label} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
 <item.icon className={`w-6 h-6 mx-auto mb-2 ${getScoreColor(item.score)}`} />
 <div className={`text-2xl font-bold ${getScoreColor(item.score)}`}>{item.score}</div>
 <div className="text-slate-400 text-sm">{item.label}</div>
 </div>
 ))}
 </motion.div>

 {/* Matched Keywords */}
 {ats.matched_keywords.length > 0 && (
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-8">
 <h2 className="text-white font-semibold text-lg mb-4 flex items-center gap-2">
 <CheckCircle2 className="w-5 h-5 text-green-400" />
 Matched Keywords
 </h2>
 <div className="flex flex-wrap gap-2">
 {ats.matched_keywords.slice(0, 15).map((kw) => (
 <span key={kw} className="bg-green-500/10 text-green-400 border border-green-500/20 px-3 py-1 rounded-lg text-sm">
 {kw}
 </span>
 ))}
 </div>
 </motion.div>
 )}

 {/* Issues */}
 {ats.issues.length > 0 && (
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-8">
 <h2 className="text-white font-semibold text-lg mb-4">Issues Found</h2>
 <ul className="space-y-2">
 {ats.issues.map((issue, i) => (
 <li key={i} className="text-slate-400 text-sm flex items-start gap-2">
 <AlertCircle className="w-4 h-4 text-yellow-400 mt-0.5 shrink-0" />
 {issue}
 </li>
 ))}
 </ul>
 </motion.div>
 )}

 {/* Optimization Suggestions by Section */}
 {data.section_optimizations.map((section, idx) => (
 <motion.div
 key={section.section}
 initial={{ opacity: 0, y: 20 }}
 animate={{ opacity: 1, y: 0 }}
 transition={{ delay: 0.35 + idx * 0.1 }}
 className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-6"
 >
 <button
 onClick={() => toggleSection(section.section)}
 className="w-full flex items-center justify-between text-left"
 >
 <h2 className="text-white font-semibold text-lg capitalize">{section.section} Optimization</h2>
 <span className="text-slate-400">
 {expandedSections[section.section] ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
 </span>
 </button>

 <AnimatePresence>
 {expandedSections[section.section] && (
 <motion.div
 initial={{ height: 0, opacity: 0 }}
 animate={{ height: 'auto', opacity: 1 }}
 exit={{ height: 0, opacity: 0 }}
 transition={{ duration: 0.3 }}
 className="overflow-hidden"
 >
 <div className="mt-4 space-y-4">
 {section.suggestions.map((s, i) => (
 <div key={i} className="bg-slate-900/50 rounded-xl p-4">
 <div className="flex items-center gap-2 mb-2">
 <span className={`text-xs px-2 py-0.5 rounded-full ${
 s.severity === 'high' ? 'bg-red-500/20 text-red-400' :
 s.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
 'bg-blue-500/20 text-blue-400'
 }`}>
 {s.severity}
 </span>
 <span className="text-slate-400 text-xs capitalize">{s.category}</span>
 <span className="text-slate-500 text-xs ml-auto">+{s.ats_impact} ATS pts</span>
 </div>
 <p className="text-slate-300 text-sm mb-2">{s.reason}</p>
 {s.original && (
 <div className="text-red-400/70 text-sm line-through mb-1">"{s.original}"</div>
 )}
 <div className="text-green-400 text-sm font-medium">"{s.suggested}"</div>
 </div>
 ))}
 {section.suggestions.length === 0 && (
 <p className="text-slate-500 text-sm">No suggestions for this section.</p>
 )}
 </div>
 </motion.div>
 )}
 </AnimatePresence>
 </motion.div>
 ))}
 </main>
 </div>
 );
}
