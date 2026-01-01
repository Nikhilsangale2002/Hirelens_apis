-- Add performance indexes to Jobs table
CREATE INDEX IF NOT EXISTS idx_user_status ON jobs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_location ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_job_type ON jobs(job_type);

-- Add performance indexes to Resumes table
CREATE INDEX IF NOT EXISTS idx_email ON resumes(email);
CREATE INDEX IF NOT EXISTS idx_job_status ON resumes(job_id, status);
CREATE INDEX IF NOT EXISTS idx_job_score ON resumes(job_id, ai_score);
CREATE INDEX IF NOT EXISTS idx_processing ON resumes(processing_status);

-- Add performance indexes to Interviews table
CREATE INDEX IF NOT EXISTS idx_access_code ON interviews(access_code);
CREATE INDEX IF NOT EXISTS idx_job_scheduled ON interviews(job_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_resume_date ON interviews(resume_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_status_date ON interviews(status, scheduled_date);
