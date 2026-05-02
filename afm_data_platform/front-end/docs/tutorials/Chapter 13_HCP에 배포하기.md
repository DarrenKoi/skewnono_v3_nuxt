# Chapter 12: 사내 클라우드에 배포하기

## 들어가며

이전 장에서는 개발 환경에서 Flask(백엔드)와 Vue(프론트엔드)를 별도의 포트에서 실행하는 방법을 배웠습니다. 이번 장에서는 **운영 환경**에서 Flask 서버가 Vue의 빌드된 정적 파일(dist 폴더)을 직접 서빙하는 **통합 배포** 방법을 알아보겠습니다.

## 1. 배포 아키텍처의 이해

### 1.1 개발 환경 vs 운영 환경

**개발 환경 (Development)**

```text
┌─────────────────┐                    ┌──────────────────┐
│   Vue Dev       │  API Request       │   Flask Dev      │
│   Server        │ ────────────────►  │   Server         │
│   (Port 3000)   │ ◄────────────────  │   (Port 5000)    │
└─────────────────┘  JSON Response     └──────────────────┘
```

**운영 환경 (Production)**

```text
┌─────────────────┐
│   사용자 브라우저  │
└────────┬────────┘
         │ HTTP Request
         ▼
┌─────────────────┐
│   Flask Server  │
│   (Port 5000)   │
├─────────────────┤
│ - API Endpoints │ ──► /api/* → API 처리
│ - Static Files  │ ──► /* → Vue 정적 파일 서빙
└─────────────────┘
```

### 1.2 통합 배포의 장점

1. **단일 서버**: 하나의 Flask 서버로 모든 요청 처리
2. **간편한 배포**: 하나의 애플리케이션만 관리
3. **CORS 불필요**: 같은 도메인에서 서비스되므로 CORS 설정 불필요
4. **보안 강화**: API와 프론트엔드가 같은 도메인에서 실행

## 2. Vue 애플리케이션 빌드

### 2.1 프로덕션 빌드 생성

Vue 애플리케이션을 배포용으로 빌드합니다:

```bash
# front-end 디렉토리로 이동
cd front-end

# 프로덕션 빌드 실행
npm run build
```

빌드가 완료되면 `front-end/dist` 폴더가 생성됩니다:

```
front-end/
└── dist/
    ├── index.html          # Vue 앱의 진입점
    ├── favicon.ico         # 파비콘
    ├── assets/            # JS, CSS, 이미지 등
    │   ├── index-xxxx.js  # 번들된 JavaScript
    │   └── index-xxxx.css # 번들된 CSS
    └── ...
```

### 2.2 환경 변수 확인

빌드 전에 `.env.production` 파일을 확인합니다:

```bash
# .env.production
VITE_API_BASE_URL=http://your-domain.skhynix.com/api  # (할당 받은 도메인 + /api)

```

## 3. Flask 서버 설정 (index.py 분석)

### 3.1 Flask 애플리케이션 생성

```python
def create_app():
    # Vue 빌드 파일이 있는지 확인
    static_folder = 'front-end/dist' if os.path.exists('front-end/dist') else None
    app = Flask(__name__, static_folder=static_folder, static_url_path='')
```

- `static_folder`: Vue 빌드 파일들이 있는 디렉토리 지정
- `static_url_path=''`: 정적 파일 경로 접두사를 비움 (기본값은 `/static`)

### 3.2 CORS 설정

```python
# 개발과 운영 환경을 위한 CORS 설정
allowed_origins = [
    'http://localhost:3000',  # Vue 개발 서버
    'http://localhost:5173',  # Vite 기본 포트
    'http://localhost:5000',  # Flask 자체
    # 운영 환경에서는 할당받은 도메인 URL 추가
    # 'http://afm-platform.skhynix.com',
]

CORS(app,
     origins=allowed_origins,
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
     supports_credentials=True
)
```

### 3.3 Vue 정적 파일 서빙

```python
# Vue 빌드 파일이 있을 때만 실행
if static_folder and os.path.exists('front-end/dist'):
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_vue_app(path):
        # API 경로는 제외
        if path.startswith('api/'):
            return {'error': 'Not found'}, 404

        # 실제 파일이 있으면 해당 파일 반환
        if path and os.path.exists(os.path.join('front-end/dist', path)):
            return send_from_directory('front-end/dist', path)

        # 그 외 모든 경로는 index.html 반환 (Vue Router가 처리)
        return send_from_directory('front-end/dist', 'index.html')
```

이 설정으로:

- `/api/*` 경로는 API 블루프린트가 처리
- 실제 파일(JS, CSS, 이미지 등)은 해당 파일 반환
- 그 외 모든 경로는 `index.html` 반환 → Vue Router가 클라이언트 측에서 라우팅 처리

## 4. HCP에 배포

HCP web app의 front-end/dist 폴더에 npm run build를 통해 생성된 파일들을 업로드합니다.

```text
afm_data_platform/
├── index.py              # Flask 진입점 (UWSGI가 찾는 파일)
├── api/                  # API 라우트
├── front-end/
│   └── dist/            # Vue 빌드 결과물
├── requirements.txt      # Python 의존성
└── uwsgi.ini            # UWSGI 설정 (선택사항)
```
