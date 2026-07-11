from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from models import Conversation, Artifact, Job, MCPServer

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    conv_id = request.args.get('c', type=int)
    conversation = None
    if conv_id:
        conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conversation:
        conversation = Conversation.query.filter_by(
            user_id=current_user.id, is_archived=False
        ).order_by(Conversation.updated_at.desc()).first()
    return render_template('dashboard.html', active_conversation=conversation)

@main_bp.route('/projects')
@login_required
def projects():
    return render_template('projects.html')

@main_bp.route('/artifacts')
@login_required
def artifacts():
    return render_template('artifacts.html')

@main_bp.route('/code')
@login_required
def code():
    return render_template('code.html')

@main_bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@main_bp.route('/mcp-settings')
@login_required
def mcp_settings():
    servers = MCPServer.query.filter_by(is_active=True).all()
    return render_template('mcp_settings.html', servers=servers)
