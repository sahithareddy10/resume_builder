'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, X, ArrowRight, Loader2 } from 'lucide-react';
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

export default function UploadPage() {
 const [file, setFile] = useState<File | null>(null);
 const [loading, setLoading] = useState(false);
 const [parsed, setParsed] = useState<ParsedResume | null>(null);
 const [taskId, setTaskId] = useState<string | null>(null);
 const [rawText, setRawText] = useState<string>("");

 const onDrop = useCallback((acceptedFiles: File[]) => {
 if (acceptedFiles.length > 0) {
 setFile(acceptedFiles[0]);
 }
 }, []);

 const { getRootProps, getInputProps, isDragActive } = useDropzone({
 onDrop,
 accept: { 'application/pdf': [], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': [], 'text/plain': [] },
 maxFiles: 1,
 maxSize: 10 * 1024 * 1024,
 });

 const handleUpload = async () => {
 if (!file) return;
 setLoading(true);

 const formData = new FormData();
 formData.append('file', file);

 try {
 const res = await fetch('/api/resume/upload', {
 method: 'POST',
 body: formData,
 });
 const data = await res.json();
 if (!res.ok) throw new Error(data.detail || data.message || 'Upload failed');

 setTaskId(data.task_id);
 setParsed(data.parsed_resume);
 // Store in sessionStorage for the optimize page
 const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(data.parsed_resume))));
 sessionStorage.setItem('resume_parsed', encoded);
 toast.success('Resume uploaded and parsed!');
 } catch (err: any) {
 toast.error(err.message || 'Upload failed');
 } finally {
 setLoading(false);
 }
 };

 const proceedToOptimize = () => {
 if (!parsed) return;
 const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(parsed))));
 // Store raw text if we have it, otherwise just the parsed data
 if (rawText) {
 sessionStorage.setItem('resume_raw', rawText);
 }
 sessionStorage.setItem('resume_parsed', encoded);
 };

 return (
 <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
 <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
 <Link href="/" className="flex items-center gap-2">
 <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
 <FileText className="w-5 h-5 text-white" />
 </div>
 <span className="text-white font-bold text-xl">ResumeAI</span>
 </Link>
 </nav>

 <main className="max-w-3xl mx-auto px-8 pt-16 pb-24">
 <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-12">
 <h1 className="text-4xl font-bold text-white mb-4">Upload Your Resume</h1>
 <p className="text-slate-400 text-lg">Upload your existing resume as PDF, DOCX, or TXT</p>
 </motion.div>

 <AnimatePresence mode="wait">
 {!parsed ? (
 <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
 <div
 {...getRootProps()}
 className={`
 border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all
 ${isDragActive ? 'border-blue-500 bg-blue-500/5' : 'border-slate-700 hover:border-slate-600'}
 `}
 >
 <input {...getInputProps()} />
 <Upload className="w-12 h-12 text-slate-500 mx-auto mb-4" />
 {file ? (
 <div className="flex items-center justify-center gap-3">
 <FileText className="w-6 h-6 text-blue-400" />
 <span className="text-white font-medium">{file.name}</span>
 <button onClick={(e) => { e.stopPropagation(); setFile(null); }} className="text-slate-500 hover:text-white">
 <X className="w-5 h-5" />
 </button>
 </div>
 ) : (
 <>
 <p className="text-white font-medium mb-1">
 {isDragActive ? 'Drop your file here' : 'Drop your resume here'}
 </p>
 <p className="text-slate-500 text-sm">or click to browse — PDF, DOCX, TXT (max 10MB)</p>
 </>
 )}
 </div>

 {file && (
 <motion.button
 initial={{ opacity: 0, y: 10 }}
 animate={{ opacity: 1, y: 0 }}
 onClick={handleUpload}
 disabled={loading}
 className="w-full mt-6 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white py-4 rounded-xl font-semibold text-lg transition-all flex items-center justify-center gap-2"
 >
 {loading ? (
 <>
 <Loader2 className="w-5 h-5 animate-spin" />
 Parsing Resume...
 </>
 ) : (
 <>
 Continue
 <ArrowRight className="w-5 h-5" />
 </>
 )}
 </motion.button>
 )}
 </motion.div>
 ) : (
 <motion.div key="parsed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
 <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
 <h2 className="text-white font-semibold text-lg mb-4 flex items-center gap-2">
 <FileText className="w-5 h-5 text-green-400" />
 Resume Parsed Successfully
 </h2>
 <div className="grid grid-cols-2 gap-4 text-sm">
 <div>
 <span className="text-slate-400">Name:</span>
 <span className="text-white ml-2">{parsed.contact.name}</span>
 </div>
 {parsed.contact.email && (
 <div>
 <span className="text-slate-400">Email:</span>
 <span className="text-white ml-2">{parsed.contact.email}</span>
 </div>
 )}
 <div>
 <span className="text-slate-400">Experience entries:</span>
 <span className="text-white ml-2">{parsed.experience.length}</span>
 </div>
 <div>
 <span className="text-slate-400">Skills found:</span>
 <span className="text-white ml-2">{parsed.skills.length}</span>
 </div>
 <div>
 <span className="text-slate-400">Word count:</span>
 <span className="text-white ml-2">{parsed.word_count}</span>
 </div>
 <div>
 <span className="text-slate-400">Pages:</span>
 <span className="text-white ml-2">{parsed.page_count}</span>
 </div>
 </div>
 </div>

 <Link
 href="/optimize"
 onClick={proceedToOptimize}
 className="block w-full bg-blue-600 hover:bg-blue-500 text-white py-4 rounded-xl font-semibold text-lg transition-all text-center"
 >
 Continue to Job Details
 <ArrowRight className="w-5 h-5 inline ml-2" />
 </Link>
 </motion.div>
 )}
 </AnimatePresence>
 </main>
 </div>
 );
}
