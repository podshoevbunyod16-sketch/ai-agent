import threading
import logging
from datetime import datetime
from models import db, Job, MCPServer
from services.mcp_client import mcp_client

logger = logging.getLogger(__name__)

# Хранилище активных потоков
active_jobs = {}
jobs_lock = threading.Lock()

def execute_job(job_id, app):
    """Фоновая задача"""
    with app.app_context():
        job = Job.query.get(job_id)
        if not job:
            return
        try:
            job.status = 'running'
            db.session.commit()

            # Найти MCP сервер
            server_url = "http://localhost:8000/mcp"
            auth_token = None
            if job.mcp_server:
                try:
                    # mcp_server может быть ID или именем/url
                    mcp = MCPServer.query.filter(
                        (MCPServer.name == job.mcp_server) |
                        (MCPServer.url == job.mcp_server) |
                        (MCPServer.id == job.mcp_server if str(job.mcp_server).isdigit() else False)
                    ).first()
                    if mcp:
                        server_url = mcp.url
                        auth_token = mcp.auth_token
                    else:
                        server_url = job.mcp_server
                except Exception:
                    pass

            result = mcp_client.call(server_url, auth_token, job.prompt)
            job.result = result
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"Job {job_id} completed")
        except Exception as e:
            logger.exception(f"Job {job_id} failed")
            job.status = 'failed'
            job.result = f"Error: {str(e)}"
            job.completed_at = datetime.utcnow()
            db.session.commit()
        finally:
            with jobs_lock:
                active_jobs.pop(job_id, None)

def start_job_async(job_id, app):
    with jobs_lock:
        if job_id in active_jobs:
            return False
        thread = threading.Thread(target=execute_job, args=(job_id, app), daemon=True)
        active_jobs[job_id] = thread
        thread.start()
        return True
