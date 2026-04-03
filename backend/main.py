from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.routes import router as api_router
from config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return """
        <!doctype html>
        <html>
            <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>Lecture Intelligence System</title>
                <style>
                    body { font-family: Inter, Arial, sans-serif; margin: 0; padding: 40px; background: #0b1020; color: #e8ecff; }
                    .card { max-width: 760px; margin: 0 auto; background: #131a31; border: 1px solid #27304f; border-radius: 16px; padding: 28px; }
                    a { color: #83b2ff; }
                    .muted { color: #97a2d2; }
                    ul { line-height: 1.8; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Lecture Intelligence System</h1>
                    <p class="muted">Backend is running successfully.</p>
                    <ul>
                        <li><a href="/docs">API Docs</a></li>
                        <li><a href="/health">Health Check</a></li>
                        <li><a href="/api/v1/videos">Videos API</a></li>
                    </ul>
                </div>
            </body>
        </html>
        """

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
