import './App.css'
import { useMemo, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data?.detail || 'Request failed.'
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data
}

const SCORE_THRESHOLDS = {
  success: 70,
  warning: 40,
}

function getScoreTone(score) {
  if (score >= SCORE_THRESHOLDS.success) return 'success'
  if (score >= SCORE_THRESHOLDS.warning) return 'warning'
  return 'danger'
}

function getScoreLabel(score) {
  if (score >= 85) return 'Excellent'
  if (score >= 70) return 'Good'
  if (score >= 40) return 'Fair'
  return 'Poor'
}

function LoadingSpinner({ inline = false }) {
  return <span className={inline ? 'spinner spinner-inline' : 'spinner'} aria-hidden="true" />
}

function ScoreBar({ label, value }) {
  const safeValue = Math.max(0, Math.min(100, Number(value || 0)))
  const tone = getScoreTone(safeValue)
  const grade = getScoreLabel(safeValue)
  return (
    <div className="score-row">
      <div className="score-header">
        <span>{label}</span>
        <strong>
          {safeValue.toFixed(2)}% <span className={`score-pill ${tone}`}>{grade}</span>
        </strong>
      </div>
      <div className="bar-track">
        <div className={`bar-fill ${tone}`} style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  )
}

function App() {
  const [resumeFile, setResumeFile] = useState(null)
  const [resumeLoading, setResumeLoading] = useState(false)
  const [resumeResult, setResumeResult] = useState(null)
  const [resumes, setResumes] = useState([])

  const [jobMode, setJobMode] = useState('manual')
  const [jobForm, setJobForm] = useState({
    title: '',
    description: '',
    required_skills: '',
    nice_to_have_skills: '',
    raw_text: '',
    url: '',
  })
  const [jobLoading, setJobLoading] = useState(false)
  const [jobResult, setJobResult] = useState(null)
  const [jobs, setJobs] = useState([])

  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [selectedJobId, setSelectedJobId] = useState('')
  const [matchLoading, setMatchLoading] = useState(false)
  const [matchResult, setMatchResult] = useState(null)

  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidates, setCandidates] = useState([])
  const [apiError, setApiError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const setSuccess = (message) => {
    setSuccessMessage(message)
    setTimeout(() => setSuccessMessage(''), 3500)
  }

  const resumeOptions = useMemo(
    () =>
      resumes.map((r) => ({
        id: r.id,
        label: `${r.candidate_name || 'Unknown Candidate'} (${r.filename})`,
      })),
    [resumes],
  )

  const jobOptions = useMemo(
    () =>
      jobs.map((j) => ({
        id: j.id,
        label: `${j.title || 'Untitled Role'} (${j.source || 'manual'})`,
      })),
    [jobs],
  )

  const parseSkillList = (value) =>
    value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)

  const onUploadResume = async (event) => {
    event.preventDefault()
    if (!resumeFile) {
      setApiError('Please choose a resume file.')
      return
    }
    setApiError('')
    setResumeLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', resumeFile)
      const data = await apiRequest('/api/resume/upload', { method: 'POST', body: formData })
      setResumeResult(data)
      setResumes((prev) => [data, ...prev.filter((item) => item.id !== data.id)])
      setSelectedResumeId(data.id)
      setSuccess('Resume uploaded successfully.')
    } catch (error) {
      setApiError(error.message)
    } finally {
      setResumeLoading(false)
    }
  }

  const onCreateJob = async (event) => {
    event.preventDefault()
    setApiError('')
    setJobLoading(true)
    try {
      let payload = {}
      if (jobMode === 'manual') {
        payload = {
          title: jobForm.title,
          description: jobForm.description,
          required_skills: parseSkillList(jobForm.required_skills),
          nice_to_have_skills: parseSkillList(jobForm.nice_to_have_skills),
        }
      } else if (jobMode === 'raw_text') {
        payload = {
          raw_text: jobForm.raw_text,
          title: jobForm.title || undefined,
          description: jobForm.description || undefined,
        }
      } else {
        payload = {
          url: jobForm.url,
          title: jobForm.title || undefined,
          description: jobForm.description || undefined,
        }
      }

      const data = await apiRequest('/api/job/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      setJobResult(data)
      setJobs((prev) => [data, ...prev.filter((item) => item.id !== data.id)])
      setSelectedJobId(data.id)
      setSuccess('Job created successfully.')
    } catch (error) {
      setApiError(error.message)
    } finally {
      setJobLoading(false)
    }
  }

  const onRunMatch = async (event) => {
    event.preventDefault()
    if (!selectedResumeId || !selectedJobId) {
      setApiError('Pick both a resume and a job before running match.')
      return
    }

    setApiError('')
    setMatchLoading(true)
    try {
      const data = await apiRequest('/api/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_id: selectedResumeId,
          job_id: selectedJobId,
        }),
      })
      setMatchResult(data)
      setSuccess('Match completed successfully.')
    } catch (error) {
      setApiError(error.message)
    } finally {
      setMatchLoading(false)
    }
  }

  const onLoadCandidates = async () => {
    if (!selectedJobId) {
      setApiError('Pick a job first to load ranked candidates.')
      return
    }
    setApiError('')
    setCandidatesLoading(true)
    try {
      const data = await apiRequest(`/api/candidates/${selectedJobId}?limit=25&min_score=0`)
      setCandidates(data.candidates || [])
      setSuccess('Candidate rankings refreshed.')
    } catch (error) {
      setApiError(error.message)
    } finally {
      setCandidatesLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>TransferATS Dashboard</h1>
          <p>Upload resumes, create jobs, and visualize candidate-job match quality.</p>
        </div>
        <code>{API_BASE_URL}</code>
      </header>

      {apiError ? <div className="error-banner">{apiError}</div> : null}
      {successMessage ? <div className="success-banner">{successMessage}</div> : null}

      <main className="grid">
        <section className="card">
          <h2>1) Resume Upload</h2>
          <form onSubmit={onUploadResume} className="stack">
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(event) => setResumeFile(event.target.files?.[0] || null)}
            />
            <button type="submit" disabled={resumeLoading}>
              {resumeLoading ? (
                <>
                  <LoadingSpinner inline /> Uploading...
                </>
              ) : (
                'Upload Resume'
              )}
            </button>
          </form>

          {resumeResult ? (
            <div className="result">
              <h3>Last Resume</h3>
              <p>
                <strong>{resumeResult.candidate_name || 'Unknown Candidate'}</strong>
              </p>
              <p>{resumeResult.email || 'No email extracted'}</p>
              <p>{resumeResult.skill_count} skills extracted</p>
            </div>
          ) : null}
        </section>

        <section className="card">
          <h2>2) Job Creation</h2>
          <div className="mode-row">
            <button
              type="button"
              className={jobMode === 'manual' ? 'chip active' : 'chip'}
              onClick={() => setJobMode('manual')}
            >
              Manual
            </button>
            <button
              type="button"
              className={jobMode === 'raw_text' ? 'chip active' : 'chip'}
              onClick={() => setJobMode('raw_text')}
            >
              Raw Text
            </button>
            <button
              type="button"
              className={jobMode === 'url' ? 'chip active' : 'chip'}
              onClick={() => setJobMode('url')}
            >
              URL
            </button>
          </div>

          <form onSubmit={onCreateJob} className="stack">
            <input
              placeholder="Job title (optional in raw/url mode)"
              value={jobForm.title}
              onChange={(event) => setJobForm((prev) => ({ ...prev, title: event.target.value }))}
            />
            {(jobMode === 'manual' || jobMode === 'raw_text') && (
              <textarea
                rows={5}
                placeholder={
                  jobMode === 'manual'
                    ? 'Job description (required in manual mode)'
                    : 'Paste full job posting text'
                }
                value={jobMode === 'manual' ? jobForm.description : jobForm.raw_text}
                onChange={(event) =>
                  setJobForm((prev) =>
                    jobMode === 'manual'
                      ? { ...prev, description: event.target.value }
                      : { ...prev, raw_text: event.target.value },
                  )
                }
              />
            )}
            {jobMode === 'url' && (
              <input
                type="url"
                placeholder="https://example.com/job-posting"
                value={jobForm.url}
                onChange={(event) => setJobForm((prev) => ({ ...prev, url: event.target.value }))}
              />
            )}
            {jobMode === 'manual' && (
              <>
                <input
                  placeholder="Required skills (comma separated)"
                  value={jobForm.required_skills}
                  onChange={(event) =>
                    setJobForm((prev) => ({ ...prev, required_skills: event.target.value }))
                  }
                />
                <input
                  placeholder="Nice-to-have skills (comma separated)"
                  value={jobForm.nice_to_have_skills}
                  onChange={(event) =>
                    setJobForm((prev) => ({ ...prev, nice_to_have_skills: event.target.value }))
                  }
                />
              </>
            )}
            <button type="submit" disabled={jobLoading}>
              {jobLoading ? (
                <>
                  <LoadingSpinner inline /> Creating...
                </>
              ) : (
                'Create Job'
              )}
            </button>
          </form>

          {jobResult ? (
            <div className="result">
              <h3>Last Job</h3>
              <p>
                <strong>{jobResult.title}</strong> ({jobResult.source})
              </p>
              <p>{jobResult.skill_count} required skills</p>
            </div>
          ) : null}
        </section>

        <section className="card">
          <h2>3) Match & Scores</h2>
          <form onSubmit={onRunMatch} className="stack">
            <label>
              Resume
              <select
                value={selectedResumeId}
                onChange={(event) => setSelectedResumeId(event.target.value)}
              >
                <option value="">Select resume...</option>
                {resumeOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Job
              <select value={selectedJobId} onChange={(event) => setSelectedJobId(event.target.value)}>
                <option value="">Select job...</option>
                {jobOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={matchLoading}>
              {matchLoading ? (
                <>
                  <LoadingSpinner inline /> Matching...
                </>
              ) : (
                'Run Match'
              )}
            </button>
          </form>

          {matchResult ? (
            <div className="result">
              <h3>
                {matchResult.candidate_name || 'Candidate'} vs {matchResult.job_title || 'Job'}
              </h3>
              <ScoreBar label="Overall Score" value={matchResult.overall_score} />
              <ScoreBar label="ATS Score" value={matchResult.ats_score} />
              <ScoreBar label="Semantic Score" value={matchResult.semantic_score} />
              <ScoreBar label="Transferable Score" value={matchResult.transferable_score} />
              <div className="skills-grid">
                <div>
                  <h4>Matched Skills</h4>
                  <div className="chip-group">
                    {(matchResult.matched_skills || []).length > 0 ? (
                      (matchResult.matched_skills || []).map((skill) => (
                        <span key={`matched-${skill}`} className="skill-chip matched">
                          {skill}
                        </span>
                      ))
                    ) : (
                      <span className="muted">No matched skills detected.</span>
                    )}
                  </div>
                </div>
                <div>
                  <h4>Missing Skills</h4>
                  <div className="chip-group">
                    {(matchResult.missing_skills || []).length > 0 ? (
                      (matchResult.missing_skills || []).map((skill) => (
                        <span key={`missing-${skill}`} className="skill-chip missing">
                          {skill}
                        </span>
                      ))
                    ) : (
                      <span className="muted">No missing skills.</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <section className="card full-width">
          <div className="split-header">
            <h2>Ranked Candidates</h2>
            <button type="button" onClick={onLoadCandidates} disabled={candidatesLoading}>
              {candidatesLoading ? (
                <>
                  <LoadingSpinner inline /> Refreshing...
                </>
              ) : (
                'Load Candidates'
              )}
            </button>
          </div>

          {candidates.length === 0 ? (
            <p className="muted">No candidates loaded yet. Run a match first, then refresh rankings.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Candidate</th>
                    <th>Email</th>
                    <th>Overall</th>
                    <th>ATS</th>
                    <th>Semantic</th>
                    <th>Transferable</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate) => (
                    <tr key={candidate.match_id}>
                      <td>#{candidate.rank}</td>
                      <td>{candidate.candidate_name || 'Unknown'}</td>
                      <td>{candidate.email || '-'}</td>
                      <td>{candidate.scores.overall.toFixed(2)}%</td>
                      <td>{candidate.scores.ats.toFixed(2)}%</td>
                      <td>{candidate.scores.semantic.toFixed(2)}%</td>
                      <td>{candidate.scores.transferable.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
