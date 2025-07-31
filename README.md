# Subtitle Sync Platform

A fullstack application powered by large language models (LLMs) designed to streamline subtitle-audio synchronization and subtitle generation for videos. The application supports multiple subtitle formats and languages, ensuring a user-friendly experience for uploading videos, monitoring progress, managing subtitle files, and performing corrections.

## Features

### 1. Subtitle-Audio Quality Check
- Automatic detection of subtitle formats
- Compliance with OTT platform standards
- Validation of reading speed, row count, and character count
- Verification of frame rate, language accuracy, and spelling
- Automatic correction of latency and caption overlap issues

### 2. Subtitle Generation
- AI-powered subtitle generation from video files
- Support for multiple languages
- Translation services for existing subtitles
- Real-time progress tracking

### 3. File Management
- Upload and manage video and subtitle files
- Download processed subtitle files
- Request translations to different languages
- File versioning and history

## Architecture

The platform consists of three main containers:

### Frontend Web Dashboard (React)
- **Port**: 3000
- **Framework**: React 18
- **Features**: 
  - Responsive UI for video/subtitle upload
  - Real-time job progress tracking
  - File management and download
  - Translation request interface
  - User authentication

### Backend Service (FastAPI)
- **Port**: 8000 (accessible via proxy at https://vscode-internal-29567-beta.beta01.cloud.kavia.ai/proxy/8000/)
- **Framework**: FastAPI
- **Features**:
  - RESTful API endpoints
  - File processing workflows
  - Job management and status tracking
  - Multi-language subtitle processing
  - CORS enabled for frontend communication

### Database (SQLite)
- **Framework**: SQLite
- **Features**:
  - User account management
  - Video and subtitle metadata storage
  - Job tracking and audit logs
  - File versioning

## Getting Started

### Prerequisites

- Node.js 14+ and npm
- Python 3.8+
- pip (Python package manager)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd Subtitle_Sync_Platform/BackendService
   ```

2. Install Python dependencies:
   ```bash
   pip install fastapi uvicorn python-multipart
   ```

3. Start the backend server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

   The backend will be available at: https://vscode-internal-29567-beta.beta01.cloud.kavia.ai/proxy/8000/

4. API documentation is available at: https://vscode-internal-29567-beta.beta01.cloud.kavia.ai/proxy/8000/docs

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd Subtitle_Sync_Platform/FrontendWebDashboard
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Create environment file from example:
   ```bash
   cp .env.example .env
   ```

4. Start the development server:
   ```bash
   npm start
   ```

   The frontend will be available at: https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001/

### Database Setup

1. Navigate to the database directory:
   ```bash
   cd Subtitle_Sync_Platform/Database
   ```

2. Initialize the database:
   ```bash
   python init_db.py
   ```

## API Endpoints

### File Processing
- `POST /process` - Process video and/or subtitle files
  - Parameters: `video` (file), `subtitle` (file, optional)
  - Returns: Processed subtitle file for download

### Authentication (Planned)
- `POST /auth/login` - User authentication
- `POST /auth/register` - User registration

### File Management (Planned)
- `GET /subtitles` - Get user's subtitle files
- `GET /subtitles/{id}/download` - Download subtitle file
- `POST /subtitles/{id}/translate` - Request translation

### Job Management (Planned)
- `GET /jobs/{id}/status` - Get job status
- `GET /jobs` - List user's jobs

## Supported File Formats

### Video Formats
- MP4, AVI, MOV, WMV, FLV, WebM, MKV

### Subtitle Formats
- SRT (SubRip)
- VTT (WebVTT)
- ASS (Advanced SubStation Alpha)
- SSA (SubStation Alpha)
- SBV (YouTube)

## Supported Languages

- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)
- Italian (it)
- Portuguese (pt)
- Russian (ru)

## Usage

### Subtitle Correction Workflow

1. Navigate to the "Subtitle Correction" tab
2. Upload both a video file and its corresponding subtitle file
3. Click "Run Correction" to start processing
4. Download the corrected subtitle file when processing completes

### Subtitle Generation Workflow

1. Navigate to the "Subtitle Generation" tab
2. Upload a video file
3. Select the target language for subtitle generation
4. Click "Generate Subtitles" to start processing
5. Download the generated subtitle file when processing completes

### File Management

1. Click "My Files" in the header to view your uploaded files
2. Download any previously processed subtitle files
3. Request translations by selecting a target language from the dropdown
4. Track translation progress and download completed translations

## Development

### Frontend Development

The React frontend uses:
- **React Router** for navigation
- **Axios** for API communication
- **CSS Variables** for theming
- **Responsive Design** for mobile compatibility

Key components:
- `App.js` - Main application component
- `components/Notification.js` - User notification system
- `components/ProgressTracker.js` - Job progress monitoring
- `services/api.js` - API communication layer
- `utils/fileUtils.js` - File handling utilities

### Backend Development

The FastAPI backend provides:
- **Automatic API documentation** via Swagger/OpenAPI
- **File upload handling** with validation
- **CORS middleware** for frontend communication
- **Error handling** and response formatting

### Environment Variables

Frontend (.env):
```
REACT_APP_API_BASE_URL=https://vscode-internal-29567-beta.beta01.cloud.kavia.ai/proxy/8000/
REACT_APP_SITE_URL=https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001/
```

## Deployment

### Production Build

Frontend:
```bash
cd FrontendWebDashboard
npm run build
```

Backend:
```bash
cd BackendService
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker Support (Planned)

The application is designed to support containerized deployment with Docker Compose for easy production deployment.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions, please open an issue in the repository or contact the development team.

---

**Note**: This application is designed for development and testing. For production use, additional security measures, authentication, and scaling considerations should be implemented.
