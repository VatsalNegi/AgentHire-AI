import { useCallback, useEffect, useState } from "react";
import {
  supabase,
  supabaseConfigured,
  supabaseConfigurationError,
} from "./supabaseClient";
import { authenticatedRequest } from "./api";
import AdminPanel from "./AdminPanel";
import "./App.css";

const MAX_JOB_DESCRIPTION_LENGTH = 12000;

function Icon({ name, size = 20 }) {
  const paths = {
    grid: (
      <>
        <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
        <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
        <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
        <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
      </>
    ),
    plus: (
      <>
        <path d="M12 5v14M5 12h14" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),
    briefcase: (
      <>
        <rect x="3" y="7" width="18" height="14" rx="2" />
        <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    report: (
      <>
        <path d="M4 19V5M4 19h16" />
        <path d="m7 14 3-3 3 2 5-6" />
      </>
    ),
    check: (
      <>
        <path d="m5 12 4 4L19 6" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z" />
        <path d="m19 14 .9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14Z" />
      </>
    ),
    alert: (
      <>
        <path d="M12 9v4M12 17h.01" />
        <path d="M10.3 4.8 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.8a2 2 0 0 0-3.4 0Z" />
      </>
    ),
    close: (
      <>
        <path d="m18 6-12 12M6 6l12 12" />
      </>
    ),
  };

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

function LoadingLabel({ children }) {
  return (
    <span className="loading-label">
      <span className="spinner" aria-hidden="true" />
      {children}
    </span>
  );
}

function EmptyList({ children }) {
  return <p className="empty-list">{children}</p>;
}

function InterviewWorkspace({
  accessToken,
  userEmail,
  profile,
  onSignOut,
  onSessionExpired,
  onNavigateAdmin,
}) {
  const [stage, setStage] = useState("dashboard");
  const [jobTitle, setJobTitle] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [session, setSession] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [result, setResult] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const questions = session?.questions ?? [];
  const currentQuestion = questions[questionIndex];
  const answeredCount =
    stage === "review" ? questionIndex + 1 : questionIndex;
  const progress = questions.length
    ? Math.round((answeredCount / questions.length) * 100)
    : 0;
  const combinedJobDescription = [
    jobTitle.trim(),
    `Job description:\n${jobDescription.trim()}`,
  ].join("\n\n");
  const remainingDescriptionLength =
    MAX_JOB_DESCRIPTION_LENGTH -
    jobTitle.trim().length -
    "\n\nJob description:\n".length;
  const title = {
    dashboard: "Overview",
    setup: "New interview",
    answer: "Interview in progress",
    review: "Answer review",
    report: "Interview report",
  }[stage];

  async function protectedRequest(path, options) {
    return authenticatedRequest(
      path,
      options,
      accessToken,
      onSessionExpired
    );
  }

  async function handleSignOut() {
    const message = await onSignOut();
    if (message) setError(message);
  }

  function showDashboard() {
    if (window.location.hash) {
      window.history.replaceState(
        window.history.state,
        "",
        `${window.location.pathname}${window.location.search}`
      );
    }
    setError("");
    setStage("dashboard");
  }

  function showSetup() {
    setError("");
    setStage("setup");
  }

  async function startInterview(event) {
    event.preventDefault();

    if (!jobTitle.trim()) {
      setError("Add a job title to tailor your interview.");
      return;
    }

    if (!jobDescription.trim()) {
      setError("Add a job description to generate relevant questions.");
      return;
    }

    if (combinedJobDescription.length > MAX_JOB_DESCRIPTION_LENGTH) {
      setError(
        `The job title and description must total ${MAX_JOB_DESCRIPTION_LENGTH.toLocaleString()} characters or fewer.`
      );
      return;
    }

    setLoading(true);
    setError("");
    setSession(null);
    setResult(null);
    setReport(null);
    setCandidateAnswer("");
    setQuestionIndex(0);

    try {
      const data = await protectedRequest("/api/v1/interview/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: combinedJobDescription,
          number_of_questions: 5,
        }),
      });

      if (!data.session_id || !Array.isArray(data.questions)) {
        throw new Error(
          "The service returned an incomplete interview session. Please try again."
        );
      }

      if (data.questions.length === 0) {
        throw new Error(
          "No interview questions were generated. Please try again."
        );
      }

      setSession(data);
      setStage("answer");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitAnswer(event) {
    event.preventDefault();

    if (!candidateAnswer.trim()) {
      setError("Write an answer before submitting.");
      return;
    }

    if (!session || !currentQuestion) {
      setError("The current interview question could not be found. Start again.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const questionId = currentQuestion.question_id;

      if (!questionId) {
        throw new Error(
          "This question is missing its ID. Start a new interview and try again."
        );
      }

      const data = await protectedRequest(
        `/api/v1/interview/sessions/${encodeURIComponent(
          session.session_id
        )}/questions/${encodeURIComponent(questionId)}/answer`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_answer: candidateAnswer.trim(),
          }),
        }
      );

      setResult(data);

      if (questionIndex + 1 >= questions.length) {
        const finalReport = await protectedRequest(
          `/api/v1/interview/sessions/${encodeURIComponent(
            session.session_id
          )}/report`
        );

        setReport(finalReport);
        setStage("report");
      } else {
        setStage("review");
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  function continueInterview() {
    setQuestionIndex((current) => current + 1);
    setCandidateAnswer("");
    setResult(null);
    setError("");
    setStage("answer");
  }

  function resetInterview() {
    setSession(null);
    setQuestionIndex(0);
    setCandidateAnswer("");
    setResult(null);
    setReport(null);
    setError("");
    setStage("dashboard");
  }

  function renderList(items, emptyText, className) {
    if (!items?.length) {
      return <EmptyList>{emptyText}</EmptyList>;
    }

    return (
      <ul className={`feedback-list ${className}`}>
        {items.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <button
          className="brand brand-home"
          type="button"
          onClick={showDashboard}
          aria-label="AgentHire AI home"
          aria-current={stage === "dashboard" ? "page" : undefined}
        >
          <span className="brand-mark">A</span>
          <span className="brand-name">
            agenthire<span className="brand-period">.</span>
          </span>
        </button>

        <div className="sidebar-caption">WORKSPACE</div>
        <nav className="sidebar-nav">
          <button
            className={`nav-link${stage === "dashboard" ? " is-active" : ""}`}
            onClick={showDashboard}
            aria-current={stage === "dashboard" ? "page" : undefined}
            title="Overview"
          >
            <Icon name="grid" />
            <span>Overview</span>
          </button>
          <button
            className={`nav-link${stage === "setup" ? " is-active" : ""}`}
            onClick={showSetup}
            aria-current={stage === "setup" ? "page" : undefined}
            title="New interview"
          >
            <Icon name="plus" />
            <span>New interview</span>
          </button>
          {report && (
            <button
              className={`nav-link${stage === "report" ? " is-active" : ""}`}
              onClick={() => setStage("report")}
              aria-current={stage === "report" ? "page" : undefined}
              title="Interview report"
            >
              <Icon name="report" />
              <span>Latest report</span>
            </button>
          )}
        </nav>

        <div className="sidebar-bottom">
          <span className="sidebar-caption">PRACTICE WORKSPACE</span>
          <p>Private interview practice, built around your role.</p>
          <span className="sidebar-version">AGENTHIRE AI</span>
        </div>
      </aside>

      <div className="mobile-header">
        <button
          className="brand brand-home"
          type="button"
          onClick={showDashboard}
          aria-label="AgentHire AI home"
          aria-current={stage === "dashboard" ? "page" : undefined}
        >
          <span className="brand-mark">A</span>
          <span className="brand-name">
            agenthire<span className="brand-period">.</span>
          </span>
        </button>
        <span className="workspace-indicator">
          <span className="status-dot" />
          Practice workspace
        </span>
      </div>

      <div className="main-column">
        <header className="page-header">
          <div>
            <p className="breadcrumb">WORKSPACE / {title.toUpperCase()}</p>
            <h1>{title}</h1>
          </div>
          <div className="auth-controls">
            <span className="header-status">
              <span className="status-dot" />
              Practice workspace
            </span>
            <span className="user-email" title={userEmail}>
              {userEmail}
            </span>
            {profile.role === "admin" && (
              <button
                className="button button-quiet admin-nav-button"
                type="button"
                onClick={onNavigateAdmin}
              >
                Admin
              </button>
            )}
            <button
              className="button button-quiet auth-signout"
              type="button"
              onClick={handleSignOut}
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="page-content">
          {error && (
            <div className="error-banner" role="alert">
              <Icon name="alert" size={19} />
              <p>{error}</p>
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <Icon name="close" size={18} />
              </button>
            </div>
          )}

          {stage === "dashboard" && (
            <section className="dashboard-view" aria-labelledby="welcome-title">
              <div className="welcome-block">
                <div className="welcome-copy">
                  <p className="eyebrow">A CLEARER WAY TO PREPARE</p>
                  <h2 id="welcome-title">
                    Walk into your next interview
                    <br className="desktop-break" /> with a little more
                    <span> confidence.</span>
                  </h2>
                  <p className="welcome-description">
                    Practice role-specific questions, get thoughtful feedback,
                    and see where to focus next.
                  </p>
                  <button
                    className="button button-primary button-large"
                    onClick={showSetup}
                  >
                    <Icon name="plus" size={18} />
                    Start an interview
                    <Icon name="arrow" size={17} />
                  </button>
                </div>
                <div className="welcome-aside" aria-label="Interview format">
                  <span className="aside-label">YOUR PRACTICE SESSION</span>
                  <strong>5</strong>
                  <span className="aside-title">role-specific questions</span>
                  <span className="aside-rule" />
                  <span className="aside-footnote">
                    Individual feedback · Final report
                  </span>
                </div>
              </div>

              <div className="section-title-row">
                <div>
                  <p className="eyebrow">YOUR WORKSPACE</p>
                  <h2>Interview activity</h2>
                </div>
                <span className="section-context">Current browser session</span>
              </div>

              {report ? (
                <article className="activity-entry">
                  <div className="activity-icon">
                    <Icon name="briefcase" size={20} />
                  </div>
                  <div className="activity-copy">
                    <span className="activity-overline">MOST RECENT PRACTICE</span>
                    <h3>{report.job_title}</h3>
                    <p>
                      {report.answered_questions} of {report.total_questions}{" "}
                      questions answered
                    </p>
                  </div>
                  <div className="activity-score">
                    <span>AVERAGE</span>
                    <strong>
                      {report.average_score == null
                        ? "—"
                        : `${report.average_score}/10`}
                    </strong>
                  </div>
                  <button
                    className="button button-quiet activity-action"
                    onClick={() => setStage("report")}
                  >
                    View report
                    <Icon name="arrow" size={16} />
                  </button>
                </article>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <Icon name="clock" size={20} />
                  </div>
                  <div>
                    <h3>No interview history yet</h3>
                    <p>
                      Completed reports appear here during this browser
                      session. Historical sessions are not available in this
                      workspace.
                    </p>
                  </div>
                  <button className="text-button" onClick={showSetup}>
                    Start your first interview
                    <Icon name="arrow" size={16} />
                  </button>
                </div>
              )}

              {report && (
                <div className="dashboard-metrics" aria-label="Latest report">
                  <div className="metric-cell">
                    <span>QUESTIONS ANSWERED</span>
                    <strong>
                      {report.answered_questions}
                      <small>/{report.total_questions}</small>
                    </strong>
                  </div>
                  <div className="metric-cell">
                    <span>PERFORMANCE</span>
                    <strong>
                      {report.performance_percentage == null
                        ? "—"
                        : `${report.performance_percentage}%`}
                    </strong>
                  </div>
                  <div className="metric-cell">
                    <span>SESSION STATUS</span>
                    <strong className="metric-status">
                      {report.completed ? "Completed" : "In progress"}
                    </strong>
                  </div>
                </div>
              )}

              <div className="dashboard-note">
                <Icon name="spark" size={18} />
                <p>
                  <strong>Built for practice.</strong> Your feedback is
                  generated from your answers and the role description you
                  provide.
                </p>
              </div>
            </section>
          )}

          {stage === "setup" && (
            <section className="workflow-view" aria-labelledby="setup-heading">
              <div className="workflow-intro">
                <p className="eyebrow">START WITH THE ROLE</p>
                <h2 id="setup-heading">Make this practice yours.</h2>
                <p>
                  Share the role and its responsibilities. Your first five
                  questions will be shaped around that context.
                </p>
              </div>

              <form className="form-surface" onSubmit={startInterview}>
                <div className="form-section-heading">
                  <span className="form-step">01</span>
                  <div>
                    <h3>Role details</h3>
                    <p>Tell us what you’re preparing for.</p>
                  </div>
                </div>

                <div className="field-group">
                  <label htmlFor="job-title">
                    Job title <span className="required-mark">Required</span>
                  </label>
                  <input
                    id="job-title"
                    name="job-title"
                    value={jobTitle}
                    onChange={(event) => setJobTitle(event.target.value)}
                    placeholder="e.g. Senior Product Designer"
                    maxLength={200}
                    autoComplete="organization-title"
                    required
                    aria-describedby="job-title-hint"
                  />
                  <p className="field-hint" id="job-title-hint">
                    Used as the role title in your final report.
                  </p>
                </div>

                <div className="field-group">
                  <label htmlFor="job-description">
                    Job description{" "}
                    <span className="required-mark">Required</span>
                  </label>
                  <textarea
                    id="job-description"
                    name="job-description"
                    value={jobDescription}
                    onChange={(event) =>
                      setJobDescription(event.target.value)
                    }
                    placeholder="Paste the responsibilities, required skills, and experience level..."
                    rows={8}
                    maxLength={Math.max(0, remainingDescriptionLength)}
                    required
                    aria-describedby="job-description-hint"
                  />
                  <div className="field-meta" id="job-description-hint">
                    <span>
                      The more context you share, the more relevant the
                      questions.
                    </span>
                    <span>
                      {jobDescription.length.toLocaleString()}/
                      {Math.max(
                        0,
                        remainingDescriptionLength
                      ).toLocaleString()}
                    </span>
                  </div>
                </div>

                <div className="form-footer">
                  <p>
                    <Icon name="clock" size={16} />
                    5 questions · Individual feedback · Final report
                  </p>
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? (
                      <LoadingLabel>Preparing questions</LoadingLabel>
                    ) : (
                      <>
                        Begin interview
                        <Icon name="arrow" size={17} />
                      </>
                    )}
                  </button>
                </div>
              </form>
            </section>
          )}

          {(stage === "answer" || stage === "review") && currentQuestion && (
            <section
              className="workflow-view interview-view"
              aria-labelledby="interview-heading"
            >
              <div className="interview-context">
                <div>
                  <p className="eyebrow">PRACTICE SESSION</p>
                  <h2 id="interview-heading">
                    {jobTitle.trim() || "Interview"}
                  </h2>
                </div>
                <span className="question-count">
                  Question{" "}
                  <strong>
                    {questionIndex + 1}
                    <span> / {questions.length}</span>
                  </strong>
                </span>
              </div>

              <div
                className="progress-block"
                role="group"
                aria-label={`Interview progress: question ${questionIndex + 1} of ${questions.length}`}
              >
                <div className="progress-label">
                  <span>
                    {stage === "review"
                      ? "Answer evaluated"
                      : "Your progress"}
                  </span>
                  <span>
                    {answeredCount} of {questions.length} answered
                  </span>
                </div>
                <div
                  className="progress-track"
                  role="progressbar"
                  aria-label="Questions answered"
                  aria-valuenow={progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span
                    className="progress-fill"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="progress-steps" aria-hidden="true">
                  {questions.map((question, index) => (
                    <span
                      className={
                        index < answeredCount
                          ? "progress-step is-complete"
                          : index === questionIndex
                            ? "progress-step is-current"
                            : "progress-step"
                      }
                      key={question.question_id}
                    >
                      {index < answeredCount ? (
                        <Icon name="check" size={13} />
                      ) : (
                        index + 1
                      )}
                    </span>
                  ))}
                </div>
              </div>

              <article className="prompt-surface">
                <div className="prompt-meta">
                  <span className="prompt-index">
                    QUESTION {String(questionIndex + 1).padStart(2, "0")}
                  </span>
                  <span className="difficulty-label">
                    {currentQuestion.difficulty}
                  </span>
                </div>
                <h3>{currentQuestion.question}</h3>
                <p className="prompt-topic">
                  <span>Focus area</span>
                  {currentQuestion.topic}
                </p>
              </article>

              {stage === "answer" && (
                <form className="answer-form" onSubmit={submitAnswer}>
                  <div className="field-group">
                    <label htmlFor="candidate-answer">
                      Your answer{" "}
                      <span className="required-mark">Required</span>
                    </label>
                    <textarea
                      id="candidate-answer"
                      name="candidate-answer"
                      value={candidateAnswer}
                      onChange={(event) =>
                        setCandidateAnswer(event.target.value)
                      }
                      placeholder="Walk through your thinking. Include relevant details or an example."
                      rows={9}
                      maxLength={5000}
                      required
                      aria-describedby="answer-hint"
                    />
                    <div className="field-meta" id="answer-hint">
                      <span>Your answer is saved with this practice report.</span>
                      <span>{candidateAnswer.length}/5000</span>
                    </div>
                  </div>
                  <div className="answer-actions">
                    <button
                      className="button button-quiet"
                      type="button"
                      onClick={resetInterview}
                      disabled={loading}
                    >
                      End practice
                    </button>
                    <button
                      className="button button-primary"
                      type="submit"
                      disabled={loading || !candidateAnswer.trim()}
                    >
                      {loading ? (
                        <LoadingLabel>Evaluating your answer</LoadingLabel>
                      ) : (
                        <>
                          Submit answer
                          <Icon name="arrow" size={17} />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}

              {stage === "review" && result && (
                <div className="review-view" aria-live="polite">
                  <div className="score-overview">
                    <div className="score-reading">
                      <span className="score-caption">QUESTION SCORE</span>
                      <strong>{result.score}</strong>
                      <span className="score-out-of">/ 10</span>
                    </div>
                    <div className="score-detail">
                      <h3>
                        {result.next_action === "review_and_improve"
                          ? "Room to build on this answer"
                          : "A strong step forward"}
                      </h3>
                      <p>{result.feedback}</p>
                    </div>
                  </div>

                  <div className="feedback-grid">
                    <section className="feedback-section">
                      <p className="eyebrow">WHAT LANDED WELL</p>
                      <h3>Strengths</h3>
                      {renderList(
                        result.strengths,
                        "No specific strengths were returned for this answer.",
                        "strength-list"
                      )}
                    </section>
                    <section className="feedback-section">
                      <p className="eyebrow">NEXT OPPORTUNITIES</p>
                      <h3>Areas to improve</h3>
                      {renderList(
                        result.improvements,
                        "No specific improvements were returned for this answer.",
                        "improvement-list"
                      )}
                    </section>
                  </div>

                  {result.sample_answer && (
                    <section className="sample-answer">
                      <div className="sample-heading">
                        <span className="sample-icon">
                          <Icon name="spark" size={17} />
                        </span>
                        <div>
                          <p className="eyebrow">A REFERENCE POINT</p>
                          <h3>Example of a strong answer</h3>
                        </div>
                      </div>
                      <p>{result.sample_answer}</p>
                    </section>
                  )}

                  <div className="answer-actions review-actions">
                    <button
                      className="button button-quiet"
                      onClick={resetInterview}
                    >
                      End practice
                    </button>
                    <button
                      className="button button-primary"
                      onClick={continueInterview}
                    >
                      Next question
                      <Icon name="arrow" size={17} />
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}

          {stage === "report" && report && (
            <section className="workflow-view report-view">
              <div className="report-heading">
                <div>
                  <p className="eyebrow">PRACTICE SESSION COMPLETE</p>
                  <h2>{report.job_title}</h2>
                  <p>
                    {report.answered_questions} of {report.total_questions}{" "}
                    questions answered
                  </p>
                </div>
                <button
                  className="button button-quiet"
                  onClick={showDashboard}
                >
                  <Icon name="grid" size={17} />
                  Overview
                </button>
              </div>

              <div className="report-score-row">
                <div className="report-score">
                  <span className="eyebrow">OVERALL SCORE</span>
                  <div className="report-score-reading">
                    <div
                      className="report-score-ring"
                      role="img"
                      aria-label={
                        report.average_score == null
                          ? "Overall score unavailable"
                          : `Overall score ${report.average_score} out of 10`
                      }
                      style={{
                        "--score-progress": `${Math.min(
                          100,
                          Math.max(0, report.performance_percentage ?? 0)
                        )}%`,
                      }}
                    >
                      <div className="report-score-ring-copy">
                        <strong>
                          {report.average_score == null
                            ? "—"
                            : report.average_score}
                        </strong>
                        <span>/ 10</span>
                      </div>
                    </div>
                  </div>
                  <p>
                    {report.performance_percentage == null
                      ? "Score unavailable"
                      : `${report.performance_percentage}% performance`}
                  </p>
                </div>
                <div
                  className="report-score-bar"
                  role="img"
                  aria-label={
                    report.performance_percentage == null
                      ? "Overall score unavailable"
                      : `Overall performance ${report.performance_percentage} percent`
                  }
                >
                  <div className="score-bar-copy">
                    <span>Overall performance</span>
                    <strong>
                      {report.performance_percentage == null
                        ? "—"
                        : `${report.performance_percentage}%`}
                    </strong>
                  </div>
                  <div className="score-track">
                    <span
                      className="score-fill"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.max(0, report.performance_percentage ?? 0)
                        )}%`,
                      }}
                    />
                  </div>
                  <p>Based on the answers evaluated in this session.</p>
                </div>
              </div>

              <div className="report-feedback">
                <section className="feedback-section">
                  <p className="eyebrow">REPEAT THESE</p>
                  <h3>Strengths</h3>
                  {renderList(
                    report.strengths,
                    "No strengths were included in this report.",
                    "strength-list"
                  )}
                </section>
                <section className="feedback-section">
                  <p className="eyebrow">KEEP DEVELOPING</p>
                  <h3>Areas to improve</h3>
                  {renderList(
                    report.improvement_areas,
                    "No improvement areas were included in this report.",
                    "improvement-list"
                  )}
                </section>
              </div>

              <div className="question-results-heading">
                <div>
                  <p className="eyebrow">DETAILED FEEDBACK</p>
                  <h3>Question-by-question</h3>
                </div>
                <span>
                  {report.questions?.length ?? 0} questions
                </span>
              </div>

              <div className="question-results">
                {(report.questions ?? []).map((item, index) => (
                  <article
                    className="question-result"
                    key={item.question_id}
                  >
                    <div className="question-result-head">
                      <span className="question-result-index">
                        {String(item.question_order ?? index + 1).padStart(
                          2,
                          "0"
                        )}
                      </span>
                      <div className="question-result-title">
                        <span className="eyebrow">
                          {item.skill} · {item.difficulty}
                        </span>
                        <h4>{item.question}</h4>
                      </div>
                      <div className="question-result-score">
                        <span>SCORE</span>
                        <strong>
                          {item.score == null ? "—" : `${item.score}/10`}
                        </strong>
                      </div>
                    </div>

                    {item.candidate_answer && (
                      <div className="report-answer">
                        <span>Your answer</span>
                        <p>{item.candidate_answer}</p>
                      </div>
                    )}
                    {item.feedback && (
                      <div className="question-feedback-copy">
                        <span>Feedback</span>
                        <p>{item.feedback}</p>
                      </div>
                    )}

                    {(item.strengths?.length > 0 ||
                      item.improvements?.length > 0) && (
                      <div className="question-feedback-lists">
                        {item.strengths?.length > 0 && (
                          <div>
                            <span>Strengths</span>
                            {renderList(
                              item.strengths,
                              "",
                              "strength-list compact-list"
                            )}
                          </div>
                        )}
                        {item.improvements?.length > 0 && (
                          <div>
                            <span>To develop</span>
                            {renderList(
                              item.improvements,
                              "",
                              "improvement-list compact-list"
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {item.sample_answer && (
                      <details className="sample-disclosure">
                        <summary>
                          <Icon name="spark" size={16} />
                          View sample answer
                          <span className="disclosure-indicator" />
                        </summary>
                        <p>{item.sample_answer}</p>
                      </details>
                    )}
                  </article>
                ))}
              </div>

              <div className="report-footer">
                <p>
                  <Icon name="spark" size={16} />
                  Feedback is an AI-generated practice aid.
                </p>
                <button
                  className="button button-primary"
                  onClick={resetInterview}
                >
                  Start another interview
                  <Icon name="arrow" size={17} />
                </button>
              </div>
            </section>
          )}
        </main>
      </div>

      <nav
        className={`mobile-nav${report ? " has-report" : ""}`}
        aria-label="Mobile navigation"
      >
        <button
          className={`mobile-nav-link${stage === "dashboard" ? " is-active" : ""}`}
          onClick={showDashboard}
          aria-current={stage === "dashboard" ? "page" : undefined}
        >
          <Icon name="grid" size={19} />
          <span>Overview</span>
        </button>
        <button
          className={`mobile-nav-link${stage === "setup" ? " is-active" : ""}`}
          onClick={showSetup}
          aria-current={stage === "setup" ? "page" : undefined}
        >
          <Icon name="plus" size={19} />
          <span>New interview</span>
        </button>
        {report && (
          <button
            className={`mobile-nav-link${stage === "report" ? " is-active" : ""}`}
            onClick={() => setStage("report")}
            aria-current={stage === "report" ? "page" : undefined}
          >
            <Icon name="report" size={19} />
            <span>Latest report</span>
          </button>
        )}
      </nav>
    </div>
  );
}

function LandingScreen({ onSignIn, onCreateAccount }) {
  return (
    <main className="landing-screen">
      <header className="landing-nav">
        <a className="landing-brand" href="/" aria-label="AgentHire home">
          <span className="brand-mark">A</span>
          <span className="brand-name">
            agenthire<span className="brand-period">.</span>
          </span>
        </a>
        <button
          className="button button-quiet landing-nav-action"
          type="button"
          onClick={onSignIn}
        >
          Sign in
        </button>
      </header>

      <section className="landing-hero">
        <div className="landing-copy">
          <p className="landing-kicker">
            <span className="landing-kicker-dot" />
            YOUR NEXT INTERVIEW STARTS HERE
          </p>
          <h1>
            Show up ready
            <br />
            for <span>what’s next.</span>
          </h1>
          <p className="landing-description">
            Build confidence with role-specific interview practice, thoughtful
            feedback, and a clear view of what to work on next.
          </p>
          <div className="landing-actions">
            <button
              className="button button-primary landing-primary"
              type="button"
              onClick={onCreateAccount}
            >
              Start practicing
              <span aria-hidden="true">↗</span>
            </button>
            <button
              className="landing-signin-link"
              type="button"
              onClick={onSignIn}
            >
              I already have an account
            </button>
          </div>
          <div className="landing-assurance">
            <span className="landing-assurance-mark" aria-hidden="true">✓</span>
            Private practice. Your pace. Your progress.
          </div>
        </div>

        <div className="landing-visual" aria-label="A preview of an interview practice session">
          <div className="landing-orbit landing-orbit-outer" />
          <div className="landing-orbit landing-orbit-inner" />
          <div className="landing-preview-card">
            <div className="landing-preview-top">
              <span className="landing-preview-label">
                <span className="landing-live-dot" />
                PRACTICE SESSION
              </span>
              <span className="landing-preview-count">01 / 05</span>
            </div>
            <div className="landing-progress-track">
              <span />
            </div>
            <p className="landing-preview-topic">BEHAVIORAL · COLLABORATION</p>
            <h2>
              Tell me about a time you turned a challenging situation into a
              successful outcome.
            </h2>
            <div className="landing-answer-card">
              <span className="landing-answer-icon" aria-hidden="true">✳</span>
              <div>
                <strong>Feedback that moves you forward</strong>
                <p>Strengths, evidence, and a practical next step.</p>
              </div>
            </div>
            <div className="landing-preview-footer">
              <span><i /> Tailored to your role</span>
              <span>AI-powered feedback</span>
            </div>
          </div>
          <span className="landing-spark landing-spark-one" aria-hidden="true">✳</span>
          <span className="landing-spark landing-spark-two" aria-hidden="true">✦</span>
        </div>
      </section>

      <section className="landing-benefits" aria-label="How AgentHire helps">
        <article>
          <span className="landing-benefit-number">01</span>
          <div>
            <h2>Practice with purpose</h2>
            <p>Questions shaped around the role you want.</p>
          </div>
        </article>
        <article>
          <span className="landing-benefit-number">02</span>
          <div>
            <h2>Get useful feedback</h2>
            <p>See what landed and where to sharpen your answer.</p>
          </div>
        </article>
        <article>
          <span className="landing-benefit-number">03</span>
          <div>
            <h2>Keep getting better</h2>
            <p>Review your progress whenever you’re ready.</p>
          </div>
        </article>
      </section>
      <footer className="landing-footer">
        <span>agenthire<span className="brand-period">.</span></span>
        <span>Interview practice, refined.</span>
      </footer>
    </main>
  );
}

function AuthScreen({
  initialMessage,
  recovery = false,
  initialMode = "login",
  onBackHome,
}) {
  const [mode, setMode] = useState(
    recovery ? "update-password" : initialMode
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState(initialMessage || "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);

    try {
      if (!supabase) {
        throw new Error(
          "Authentication is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY."
        );
      }

      if (mode === "reset") {
        const { error: requestError } =
          await supabase.auth.resetPasswordForEmail(email.trim(), {
            redirectTo: window.location.origin,
          });
        if (requestError) throw requestError;
        setNotice("If an account exists for that email, a reset link is on its way.");
      } else if (mode === "update-password") {
        const { error: updateError } = await supabase.auth.updateUser({
          password,
        });
        if (updateError) throw updateError;
        setPassword("");
        setNotice("Your password has been updated. You are signed in.");
      } else if (mode === "signup") {
        const { data, error: signupError } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: { emailRedirectTo: window.location.origin },
        });
        if (signupError) throw signupError;
        if (!data.session) {
          setNotice("Account created. Check your email to verify your address, then sign in.");
        }
      } else {
        const { error: loginError } =
          await supabase.auth.signInWithPassword({
            email: email.trim(),
            password,
          });
        if (loginError) throw loginError;
      }
    } catch (authError) {
      setError(authError.message || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const isPasswordMode = mode === "login" || mode === "signup" || mode === "update-password";
  const heading = {
    login: "Welcome back",
    signup: "Create your account",
    reset: "Reset your password",
    "update-password": "Choose a new password",
  }[mode];
  const submitText = {
    login: "Sign in",
    signup: "Create account",
    reset: "Send reset link",
    "update-password": "Update password",
  }[mode];

  return (
    <main className="auth-screen">
      <section className="auth-panel" aria-labelledby="auth-title">
        {onBackHome && !recovery && (
          <button
            className="auth-home-link"
            type="button"
            onClick={onBackHome}
          >
            <span aria-hidden="true">←</span> Back to home
          </button>
        )}
        <div className="auth-brand" aria-label="AgentHire AI">
          <span className="brand-mark">A</span>
          <span className="brand-name">
            agenthire<span className="brand-period">.</span>
          </span>
        </div>
        <p className="eyebrow">PRIVATE INTERVIEW PRACTICE</p>
        <h1 id="auth-title">{heading}</h1>
        <p className="auth-intro">
          Practice with role-specific questions and get focused feedback.
        </p>
        {!supabaseConfigured && (
          <div className="error-banner auth-message" role="alert">
            {supabaseConfigurationError}
          </div>
        )}
        {notice && <p className="auth-notice" role="status">{notice}</p>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <form className="auth-form" onSubmit={handleSubmit}>
          {mode !== "update-password" && (
            <label className="field-group" htmlFor="auth-email">
              <span>Email address</span>
              <input
                id="auth-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
          )}
          {isPasswordMode && (
            <label className="field-group" htmlFor="auth-password">
              <span>{mode === "update-password" ? "New password" : "Password"}</span>
              <input
                id="auth-password"
                type="password"
                autoComplete={
                  mode === "signup"
                    ? "new-password"
                    : mode === "update-password"
                      ? "new-password"
                      : "current-password"
                }
                minLength={mode === "signup" || mode === "update-password" ? 8 : undefined}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
          )}
          <button
            className="button button-primary auth-submit"
            type="submit"
            disabled={loading || !supabaseConfigured}
          >
            {loading ? <LoadingLabel>Please wait</LoadingLabel> : submitText}
          </button>
        </form>
        <div className="auth-links">
          {mode === "login" && (
            <>
              <button type="button" onClick={() => { setError(""); setNotice(""); setMode("reset"); }}>
                Forgot password?
              </button>
              <span>New to AgentHire?</span>
              <button type="button" onClick={() => { setError(""); setNotice(""); setMode("signup"); }}>
                Create an account
              </button>
            </>
          )}
          {mode === "signup" && (
            <button type="button" onClick={() => { setError(""); setNotice(""); setMode("login"); }}>
              Already registered? Sign in
            </button>
          )}
          {mode === "reset" && (
            <button type="button" onClick={() => { setError(""); setNotice(""); setMode("login"); }}>
              Back to sign in
            </button>
          )}
          {mode === "update-password" && (
            <button type="button" onClick={() => { setError(""); setNotice(""); setMode("login"); }}>
              Back to sign in
            </button>
          )}
        </div>
        <p className="auth-footnote">
          Your interview sessions and reports are private to your account.
        </p>
      </section>
    </main>
  );
}

function AccessStatusScreen({
  title,
  message,
  userEmail,
  onSignOut,
  onWorkspace,
  onRetry,
}) {
  return (
    <main className="access-screen">
      <section className="access-panel">
        <div className="auth-brand" aria-label="AgentHire AI">
          <span className="brand-mark">A</span>
          <span className="brand-name">
            agenthire<span className="brand-period">.</span>
          </span>
        </div>
        <p className="eyebrow">ACCOUNT ACCESS</p>
        <h1>{title}</h1>
        <p>{message}</p>
        {userEmail && <p className="access-account">{userEmail}</p>}
        <div className="access-actions">
          {onWorkspace && (
            <button
              className="button button-primary"
              type="button"
              onClick={onWorkspace}
            >
              Back to workspace
            </button>
          )}
          {onRetry && (
            <button
              className="button button-primary"
              type="button"
              onClick={onRetry}
            >
              Try again
            </button>
          )}
          <button
            className="button button-quiet"
            type="button"
            onClick={onSignOut}
          >
            Sign out
          </button>
        </div>
      </section>
    </main>
  );
}

function App() {
  const [authSession, setAuthSession] = useState(null);
  const [authReady, setAuthReady] = useState(!supabaseConfigured);
  const [authMessage, setAuthMessage] = useState("");
  const [showAuthScreen, setShowAuthScreen] = useState(false);
  const [initialAuthMode, setInitialAuthMode] = useState("login");
  const [passwordRecovery, setPasswordRecovery] = useState(false);
  const [profileState, setProfileState] = useState({
    userId: null,
    attempt: -1,
    profile: null,
    error: "",
  });
  const [profileRetry, setProfileRetry] = useState(0);
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const profileMatchesSession =
    profileState.userId === authSession?.user?.id &&
    profileState.attempt === profileRetry;
  const profile = profileMatchesSession ? profileState.profile : null;
  const profileError = profileMatchesSession ? profileState.error : "";
  const profileLoading =
    Boolean(authSession) && !profileMatchesSession;

  useEffect(() => {
    if (!supabase) return undefined;

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      setAuthSession(session);
      if (event === "PASSWORD_RECOVERY") {
        setPasswordRecovery(true);
        setShowAuthScreen(true);
      } else if (event === "SIGNED_OUT" || event === "USER_UPDATED") {
        setPasswordRecovery(false);
        if (event === "SIGNED_OUT") setShowAuthScreen(false);
      }
      if (event === "SIGNED_IN") setAuthMessage("");
    });

    supabase.auth.getSession().then(async ({ data, error }) => {
      if (error) {
        setAuthMessage("Could not restore your sign-in. Please sign in again.");
        await supabase.auth.signOut({ scope: "local" });
      } else {
        setAuthSession(data.session);
      }
      setAuthReady(true);
    });

    return () => subscription.unsubscribe();
  }, []);

  async function signOut() {
    if (!supabase) return "Authentication is not configured.";
    try {
      const { error } = await supabase.auth.signOut();
      return error ? "Sign out could not be completed. Please try again." : "";
    } catch {
      return "Sign out could not be completed. Please try again.";
    }
  }

  const expireSession = useCallback(async () => {
    setAuthMessage("Your session expired. Sign in again to continue.");
    try {
      if (supabase) await supabase.auth.signOut({ scope: "local" });
    } finally {
      setAuthSession(null);
      setPasswordRecovery(false);
    }
  }, []);

  useEffect(() => {
    const updatePath = () => setCurrentPath(window.location.pathname);
    window.addEventListener("popstate", updatePath);
    return () => window.removeEventListener("popstate", updatePath);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const accessToken = authSession?.access_token;
    const userId = authSession?.user?.id;
    if (!accessToken || !userId || passwordRecovery) return undefined;

    authenticatedRequest(
      "/api/v1/auth/me",
      {},
      accessToken,
      expireSession
    )
      .then((currentProfile) => {
        if (!cancelled) {
          setProfileState({
            userId,
            attempt: profileRetry,
            profile: currentProfile,
            error: "",
          });
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setProfileState({
            userId,
            attempt: profileRetry,
            profile: null,
            error:
              requestError.message ||
              "Could not verify your AgentHire account access.",
          });
        }
      })

    return () => {
      cancelled = true;
    };
  }, [
    authSession?.access_token,
    authSession?.user?.id,
    passwordRecovery,
    profileRetry,
    expireSession,
  ]);

  function navigate(path) {
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
    setCurrentPath(path);
  }

  const navigateToWorkspace = () => navigate("/");
  const navigateToAdmin = () => navigate("/admin");

  if (!authReady) {
    return (
      <main className="auth-loading" aria-live="polite">
        <span className="brand-mark">A</span>
        <span className="auth-loading-label">Restoring your secure session</span>
        <span className="spinner" aria-hidden="true" />
      </main>
    );
  }

  if (!authSession || passwordRecovery) {
    if (!passwordRecovery && !showAuthScreen) {
      return (
        <LandingScreen
          onSignIn={() => {
            setInitialAuthMode("login");
            setShowAuthScreen(true);
          }}
          onCreateAccount={() => {
            setInitialAuthMode("signup");
            setShowAuthScreen(true);
          }}
        />
      );
    }

    return (
      <AuthScreen
        initialMessage={authMessage}
        recovery={passwordRecovery}
        initialMode={initialAuthMode}
        onBackHome={() => setShowAuthScreen(false)}
        key={
          passwordRecovery
            ? "password-recovery"
            : `authentication-${initialAuthMode}`
        }
      />
    );
  }

  if (profileLoading || (!profile && !profileError)) {
    return (
      <main className="auth-loading" aria-live="polite">
        <span className="brand-mark">A</span>
        <span className="auth-loading-label">Checking application access</span>
        <span className="spinner" aria-hidden="true" />
      </main>
    );
  }

  if (profileError) {
    return (
      <AccessStatusScreen
        title="Could not verify access"
        message={profileError}
        userEmail={authSession.user?.email || ""}
        onSignOut={() => void signOut()}
        onRetry={() => setProfileRetry((value) => value + 1)}
      />
    );
  }

  if (!profile?.is_active) {
    return (
      <AccessStatusScreen
        title="Access not granted"
        message="Your account is signed in, but an administrator must grant application access before you can use the interview workspace."
        userEmail={authSession.user?.email || ""}
        onSignOut={() => void signOut()}
        onRetry={() => setProfileRetry((value) => value + 1)}
      />
    );
  }

  if (currentPath === "/admin") {
    if (profile.role !== "admin") {
      return (
        <AccessStatusScreen
          title="Administrator access required"
          message="Your account does not have permission to view user management."
          userEmail={authSession.user?.email || ""}
          onSignOut={() => void signOut()}
          onWorkspace={navigateToWorkspace}
        />
      );
    }
    return (
      <AdminPanel
        accessToken={authSession.access_token}
        currentUserId={profile.id}
        onSessionExpired={expireSession}
        onWorkspace={navigateToWorkspace}
      />
    );
  }

  return (
    <InterviewWorkspace
      accessToken={authSession.access_token}
      userEmail={authSession.user?.email || ""}
      profile={profile}
      onSignOut={signOut}
      onSessionExpired={expireSession}
      onNavigateAdmin={navigateToAdmin}
    />
  );
}

export default App;
