"""Celery tasks. Each runs inside a Flask app context for DB access.

Flow (TZ §2):
  process_prompt  -> LLM storyboard + VO draft, status=awaiting_user (bot shows buttons)
  render_final    -> build composition + render via OpenMontage, status=done
"""
import json
import logging

from .celery_app import celery
from .models import db, Job
from . import llm, render, asr

log = logging.getLogger("videobot.tasks")


def _app():
    # Imported lazily to avoid circular import at module load.
    from . import create_app
    return create_app()


def _notify(job):
    """Best-effort push of a status change back to the user via their bot."""
    try:
        from bots.notify import notify_job  # optional; safe if bots not running
        notify_job(job)
    except Exception as e:  # noqa: BLE001
        log.exception("notify failed: %s", e)


def _run_storyboard(job):
    """Generate storyboard + VO draft for a job and move it to awaiting_user."""
    job.status = "processing"
    db.session.commit()
    storyboard, vo = llm.generate_storyboard(job.prompt or "", job.corrections or "")
    job.storyboard_json = json.dumps(storyboard, ensure_ascii=False)
    job.vo_draft = vo
    job.status = "awaiting_user"
    db.session.commit()
    _notify(job)
    return storyboard


@celery.task(bind=True, name="app.tasks.process_prompt")
def process_prompt(self, job_id):
    app = _app()
    with app.app_context():
        job = db.session.get(Job, job_id)
        if not job:
            return {"error": "job not found"}
        job.celery_id = self.request.id
        db.session.commit()
        try:
            sb = _run_storyboard(job)
            return {"ok": True, "offline": sb.get("_offline", False)}
        except Exception as e:  # noqa: BLE001
            job.status = "error"; job.error = str(e); db.session.commit(); _notify(job)
            raise


@celery.task(bind=True, name="app.tasks.process_voice_prompt")
def process_voice_prompt(self, job_id):
    """Transcribe the job's voice message (heavy CPU → same queue), then build the storyboard."""
    app = _app()
    with app.app_context():
        job = db.session.get(Job, job_id)
        if not job:
            return {"error": "job not found"}
        job.celery_id = self.request.id
        job.status = "transcribing"
        db.session.commit()
        try:
            text = asr.transcribe(job.voice_path)
            job.prompt = (job.prompt + "\n" if job.prompt else "") + text
            db.session.commit()
            sb = _run_storyboard(job)
            return {"ok": True, "text": text}
        except Exception as e:  # noqa: BLE001
            job.status = "error"; job.error = str(e); db.session.commit(); _notify(job)
            raise


@celery.task(bind=True, name="app.tasks.transcribe_audio")
def transcribe_audio(self, audio_path):
    """Standalone transcription for the external API — runs on the same single-thread queue."""
    return {"text": asr.transcribe(audio_path)}


@celery.task(bind=True, name="app.tasks.render_final")
def render_final(self, job_id):
    app = _app()
    with app.app_context():
        job = db.session.get(Job, job_id)
        if not job:
            return {"error": "job not found"}
        job.celery_id = self.request.id
        job.status = "rendering"
        db.session.commit()
        _notify(job)
        try:
            storyboard = json.loads(job.storyboard_json or "{}")
            gender = "male"  # bot/style could override; default onyx-style male
            out = render.render_job(job, storyboard, gender=gender)
            job.output_path = out
            job.status = "done"
            db.session.commit()
            _notify(job)
            return {"ok": True, "output": out}
        except Exception as e:  # noqa: BLE001
            job.status = "error"
            job.error = str(e)
            db.session.commit()
            _notify(job)
            raise
