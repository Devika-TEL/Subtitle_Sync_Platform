# SubtitleSync - Frontend Web Dashboard

A comprehensive React-based frontend for the Subtitle Sync Platform, providing AI-powered subtitle processing, editing, and management capabilities.

## Features

### Core Functionality
- **🎬 Video & Subtitle Upload**: Support for multiple video and subtitle formats
- **🤖 AI Subtitle Generation**: Generate subtitles from video using LLM technology
- **🔧 Smart Correction**: Automatically fix timing, overlaps, and quality issues
- **✏️ In-Browser Editor**: Full-featured subtitle editor with video playback synchronization
- **🌐 Multi-Language Support**: Translation and management of subtitles in multiple languages
- **📁 File Management**: Organize, download, and manage subtitle files
- **📊 Real-Time Progress**: Monitor processing jobs with live status updates

### User Experience
- **📱 Responsive Design**: Optimized for desktop, tablet, and mobile devices
- **♿ Accessibility**: Full keyboard navigation and screen reader support
- **🎨 Modern UI**: Beautiful gradient-based design with smooth animations
- **🔔 Smart Notifications**: Context-aware notifications with auto-dismiss
- **🛡️ Error Handling**: Comprehensive error boundaries and user-friendly error messages

### Technical Features
- **🔐 Authentication**: Secure user authentication and session management
- **⚡ Performance**: Optimized file handling and lazy loading
- **🔄 Real-Time Updates**: WebSocket support for live progress tracking
- **📦 Component Architecture**: Modular, reusable React components
- **🎯 Type Safety**: Comprehensive prop validation and error handling

## Technology Stack

- **Frontend Framework**: React 18.2.0
- **Routing**: React Router DOM 6.8.0
- **HTTP Client**: Axios 1.6.0
- **Styling**: CSS3 with CSS Custom Properties
- **Build Tool**: Create React App
- **Testing**: React Testing Library

## Quick Start

### Prerequisites
- Node.js 16+ 
- npm or yarn
- Backend service running on port 3001 (default)

### Installation
```bash
# Install dependencies
npm install

# Start development server
npm start

# Open browser to http://localhost:3000
```

### Environment Variables
Create a `.env` file in the root directory:

```env
# Backend API Configuration
REACT_APP_API_BASE_URL=http://localhost:3001

# Optional: Error Reporting
REACT_APP_ERROR_REPORTING_URL=https://your-error-service.com/api/errors

# Optional: Site URL for redirects
REACT_APP_SITE_URL=http://localhost:3000
```

## Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── AuthPage/        # Authentication pages
│   ├── ErrorBoundary/   # Error handling
│   ├── Notification/    # Basic notifications
│   ├── NotificationSystem/ # Enhanced notification system
│   ├── ProgressTracker/ # Job progress monitoring
│   ├── Register/        # User registration
│   └── SubtitleEditor/  # In-browser subtitle editor
├── contexts/            # React Context providers
│   └── AuthContext.js   # Authentication state management
├── services/            # API and external services
│   └── api.js          # Backend API client
├── utils/               # Utility functions
│   ├── fileUtils.js    # File handling utilities
│   └── subtitleUtils.js # Subtitle processing utilities
├── App.js              # Main application component
├── App.css             # Global styles and CSS variables
└── index.js            # Application entry point
```

## Component Documentation

### Dashboard
The main application interface providing:
- File upload workflows (generation & correction)
- Progress monitoring
- File management
- Subtitle editor integration

### SubtitleEditor
Full-featured in-browser subtitle editor with:
- Video playback synchronization
- Real-time subtitle timing
- Text editing capabilities
- Format validation
- Export functionality

### AuthPage  
Unified authentication interface supporting:
- User login
- User registration
- Form validation
- Error handling

### NotificationSystem
Advanced notification system featuring:
- Multiple notification types (success, error, warning, info)
- Auto-dismiss functionality
- Progress indicators
- Responsive positioning

## API Integration

The frontend integrates with the FastAPI backend through several endpoints:

### Core Endpoints
- `POST /process` - Process videos and subtitles
- `GET /subtitles` - List user subtitle files
- `GET /subtitles/{id}/download` - Download subtitle files
- `POST /subtitles/{id}/translate` - Request translations
- `GET /jobs/{id}/status` - Monitor job progress

### Authentication
- `POST /auth/login` - User authentication
- `POST /auth/register` - User registration

## Supported File Formats

### Video Formats
- MP4, AVI, MOV, MKV, WebM

### Subtitle Formats
- SRT (SubRip)
- VTT (WebVTT)
- ASS (Advanced SubStation Alpha)
- SSA (SubStation Alpha)
- SCC (Scenarist Closed Caption)
- SUB (MicroDVD)
- SMI/SAMI (Synchronized Accessible Media Interchange)

## Responsive Design

The application is fully responsive with breakpoints:
- **Desktop**: > 1024px - Full feature layout
- **Tablet**: 768px - 1024px - Adaptive layout
- **Mobile**: < 768px - Stacked layout with optimized touch targets

## Accessibility Features

- **Keyboard Navigation**: Full keyboard support for all interactive elements
- **Screen Reader Support**: Proper ARIA labels and semantic HTML
- **High Contrast**: Support for high contrast mode
- **Reduced Motion**: Respects user's motion preferences
- **Focus Management**: Clear focus indicators and logical tab order

## Error Handling

The application includes comprehensive error handling:

### ErrorBoundary
- Catches JavaScript errors in component tree
- Provides fallback UI with recovery options
- Reports errors to external services (configurable)
- Development mode shows detailed error information

### API Error Handling
- Network error detection and retry logic
- User-friendly error messages
- Automatic token refresh for authentication errors
- Graceful degradation for offline scenarios

## Performance Optimization

- **Code Splitting**: Lazy loading of non-critical components
- **Image Optimization**: Responsive images with proper sizing
- **Bundle Optimization**: Tree shaking and minification
- **Caching**: Intelligent API response caching
- **Virtual Scrolling**: For large file lists

## Development

### Available Scripts
```bash
# Start development server
npm start

# Run tests
npm test

# Build for production
npm run build

# Eject (not recommended)
npm run eject
```

### Code Style
- ESLint configuration for code quality
- Prettier integration for consistent formatting
- Component documentation with JSDoc
- PropTypes for type checking

### Testing
```bash
# Run all tests
npm test

# Run tests with coverage
npm test -- --coverage

# Run tests in watch mode
npm test -- --watch
```

## Deployment

### Production Build
```bash
# Create optimized production build
npm run build

# Serve locally for testing
npx serve -s build
```

### Environment Configuration
Set appropriate environment variables for production:
- `REACT_APP_API_BASE_URL`: Production backend URL
- `REACT_APP_SITE_URL`: Production frontend URL

### Docker Support
```dockerfile
FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npx", "serve", "-s", "build"]
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Create Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the GitHub repository
- Check the documentation wiki
- Contact the development team

---

**SubtitleSync Frontend** - Transforming video accessibility with AI-powered subtitle processing.
