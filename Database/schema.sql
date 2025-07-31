-- SQLite schema for Subtitle Sync Platform

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY,
    uploader_id INTEGER,
    filename TEXT NOT NULL,
    original_path TEXT,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration INTEGER,
    file_size INTEGER,
    title TEXT,
    description TEXT,
    language TEXT,
    FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    video_id INTEGER,
    type TEXT CHECK( type IN ('correction', 'generation') ) NOT NULL,
    status TEXT CHECK( status IN ('pending','in_progress','success','error','cancelled')) DEFAULT 'pending',
    requested_language TEXT,
    input_subtitle_id INTEGER,
    output_subtitle_id INTEGER,
    progress INTEGER DEFAULT 0,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    finished_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS subtitles (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    is_original BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    creator_job_id INTEGER,
    user_id INTEGER,
    notes TEXT,
    FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY(creator_job_id) REFERENCES jobs(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE UNIQUE INDEX idx_video_lang_version ON subtitles(video_id, language, version);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    session_token TEXT NOT NULL UNIQUE,
    login_ip TEXT,
    user_agent TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    event_type TEXT,
    event_details TEXT,
    event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
