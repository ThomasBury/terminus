from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from terminus.config import settings

router = APIRouter()


@router.get("/", response_class=HTMLResponse, tags=["UI"])
async def homepage():
    return f"""
    <html>
        <head><title>Terminus API</title></head>
        <body style="font-family:Arial, sans-serif;">
            <h1>📖🧠 Terminus</h1>
            <p><strong>LLM-powered terminology API</strong> for the user-defined domain: <b>{settings.topic_domain}</b>.</p>
            <p>Use <a href="/docs">/docs</a> to explore the API.</p>
            <p><i>Try defining a term like <code>/definition/inflation</code></i></p>
        </body>
    </html>
    """


@router.get("/about", response_class=HTMLResponse, tags=["UI"])
async def about():
    return f"""
    <html>
        <head><title>About Terminus</title></head>
        <body style="font-family:Arial, sans-serif; max-width: 720px; margin: auto;">
            <h1>🧠 About Terminus</h1>
            <p><strong>Terminus</strong> is a full-stack FastAPI application that enriches, critiques, and serves LLM-generated definitions for the <b>{settings.topic_domain}</b> domain (user-defined).</p>
            <p>It integrates:</p>
            <ul>
                <li>📚 <strong>Wikipedia</strong> for seed definitions</li>
                <li>🤖 <strong>LLMs</strong> for validation and enrichment</li>
                <li>📌 <strong>Follow-up questions</strong> for deeper exploration</li>
                <li>🧪 <strong>Self-evaluation</strong> with schema validation</li>
            </ul>
            <p><a href="/docs">Visit API docs</a> or see the README for more info.</p>
        </body>
    </html>
    """
