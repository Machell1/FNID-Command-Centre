"""
Document Upload & Management Routes

Allows officers to upload, view, and manage documents (PDF, DOCX, images, Excel).
"""

import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..models import get_db, log_audit
from ..rbac import role_required

bp = Blueprint("documents", __name__, url_prefix="/documents")

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "jpg", "jpeg", "png", "xlsx", "xls"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route("/")
@login_required
def doc_list():
    """List documents - own for regular users, all for admin/dco."""
    conn = get_db()
    try:
        role = getattr(current_user, "role", "io")
        if role in ("admin", "dco", "ddi"):
            docs = conn.execute(
                "SELECT * FROM member_documents ORDER BY uploaded_at DESC"
            ).fetchall()
        else:
            docs = conn.execute(
                "SELECT * FROM member_documents WHERE uploaded_by = ? ORDER BY uploaded_at DESC",
                (current_user.badge_number,)
            ).fetchall()
        return render_template("documents/list.html", documents=docs)
    finally:
        conn.close()


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload a new document."""
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for("documents.upload"))

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.", "danger")
            return redirect(url_for("documents.upload"))

        if not _allowed_file(file.filename):
            flash(f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}", "danger")
            return redirect(url_for("documents.upload"))

        safe_name = secure_filename(file.filename)
        ext = safe_name.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"

        doc_dir = os.path.join(current_app.config.get("UPLOAD_DIR", "data/uploads"), "documents")
        os.makedirs(doc_dir, exist_ok=True)
        filepath = os.path.join(doc_dir, stored_name)
        file.save(filepath)

        file_size = os.path.getsize(filepath)
        title = request.form.get("title", safe_name).strip() or safe_name
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "General").strip()

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO member_documents
                (title, original_filename, stored_filename, file_size, file_type,
                 category, description, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, safe_name, stored_name, file_size, ext,
                  category, description, current_user.badge_number,
                  datetime.now().isoformat()))
            conn.commit()
            log_audit("member_documents", stored_name, "UPLOAD",
                      current_user.badge_number, current_user.full_name,
                      f"Uploaded: {safe_name}")
        finally:
            conn.close()

        flash(f"Document '{title}' uploaded successfully.", "success")
        return redirect(url_for("documents.doc_list"))

    return render_template("documents/upload.html")


@bp.route("/<int:doc_id>/download")
@login_required
def download(doc_id):
    """Download a document (owner or admin only)."""
    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT * FROM member_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not doc:
            flash("Document not found.", "danger")
            return redirect(url_for("documents.doc_list"))

        role = getattr(current_user, "role", "io")
        if doc["uploaded_by"] != current_user.badge_number and role not in ("admin", "dco", "ddi"):
            flash("Access denied.", "danger")
            return redirect(url_for("documents.doc_list"))

        doc_dir = os.path.join(current_app.config.get("UPLOAD_DIR", "data/uploads"), "documents")
        filepath = os.path.join(doc_dir, doc["stored_filename"])

        if not os.path.exists(filepath):
            flash("File not found on disk.", "danger")
            return redirect(url_for("documents.doc_list"))

        return send_file(filepath, as_attachment=True, download_name=doc["original_filename"])
    finally:
        conn.close()


@bp.route("/<int:doc_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "dco")
def delete(doc_id):
    """Delete a document (admin/DCO only)."""
    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT * FROM member_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not doc:
            flash("Document not found.", "danger")
            return redirect(url_for("documents.doc_list"))

        doc_dir = os.path.join(current_app.config.get("UPLOAD_DIR", "data/uploads"), "documents")
        filepath = os.path.join(doc_dir, doc["stored_filename"])
        if os.path.exists(filepath):
            os.remove(filepath)

        conn.execute("DELETE FROM member_documents WHERE id = ?", (doc_id,))
        conn.commit()
        log_audit("member_documents", str(doc_id), "DELETE",
                  current_user.badge_number, current_user.full_name,
                  f"Deleted: {doc['original_filename']}")
        flash("Document deleted.", "success")
    finally:
        conn.close()
    return redirect(url_for("documents.doc_list"))
