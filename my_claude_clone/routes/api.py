from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Conversation, Message, Artifact, Project, Job, MCPServer, project_conversations
from services.ai_client import ai_client, extract_artifacts
from services.job_executor import start_job_async
from datetime import datetime
import re

api_bp = Blueprint('api', __name__, url_prefix='/api')

def to_dict_conv(c):
    return {
        'id': c.id,
        'title': c.title,
        'updated_at': c.updated_at.isoformat(),
        'is_favorite': c.is_favorite,
        'is_archived': c.is_archived
    }

# Conversations
@api_bp.route('/conversations', methods=['GET'])
@login_required
def list_conversations():
    q = request.args.get('q', '').strip()
    query = Conversation.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(Conversation.title.ilike(f'%{q}%'))
    convs = query.order_by(Conversation.updated_at.desc()).all()
    return jsonify([to_dict_conv(c) for c in convs])

@api_bp.route('/conversations', methods=['POST'])
@login_required
def create_conversation():
    data = request.get_json() or {}
    title = data.get('title', 'Новый чат')[:200]
    c = Conversation(user_id=current_user.id, title=title)
    db.session.add(c)
    db.session.commit()
    return jsonify(to_dict_conv(c)), 201

@api_bp.route('/conversations/<int:cid>', methods=['PUT'])
@login_required
def update_conversation(cid):
    c = Conversation.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    data = request.get_json() or {}
    if 'title' in data:
        c.title = data['title'][:200]
    if 'is_favorite' in data:
        c.is_favorite = bool(data['is_favorite'])
    if 'is_archived' in data:
        c.is_archived = bool(data['is_archived'])
    db.session.commit()
    return jsonify(to_dict_conv(c))

@api_bp.route('/conversations/<int:cid>', methods=['DELETE'])
@login_required
def delete_conversation(cid):
    c = Conversation.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    db.session.delete(c)
    db.session.commit()
    return jsonify({'ok': True})

@api_bp.route('/conversations/<int:cid>/messages', methods=['GET'])
@login_required
def get_messages(cid):
    c = Conversation.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    msgs = [{
        'id': m.id,
        'role': m.role,
        'content': m.content,
        'created_at': m.created_at.isoformat(),
        'artifacts': [{'id': a.id, 'title': a.title, 'language': a.language} for a in m.artifacts]
    } for m in c.messages]
    return jsonify(msgs)

@api_bp.route('/conversations/<int:cid>/messages', methods=['POST'])
@login_required
def post_message(cid):
    c = Conversation.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    extended_thinking = bool(data.get('extended_thinking', False))
    model = data.get('model', 'claude-3.5-sonnet')
    if not content:
        return jsonify({'error': 'empty content'}), 400

    # save user message
    um = Message(conversation_id=c.id, role='user', content=content)
    db.session.add(um)
    c.updated_at = datetime.utcnow()
    # auto title from first message
    if c.title == 'Новый чат' and len(c.messages) == 0:
        c.title = (content[:50] + '...') if len(content) > 50 else content
    db.session.commit()

    # build history
    history = [{'role': m.role, 'content': m.content} for m in c.messages]
    if extended_thinking:
        history.insert(0, {'role': 'system', 'content': 'Use extended thinking. Think step by step carefully.'})

    # call AI
    answer = ai_client.chat(history)

    am = Message(conversation_id=c.id, role='assistant', content=answer)
    db.session.add(am)
    db.session.flush()

    # extract artifacts
    arts = extract_artifacts(answer)
    saved_arts = []
    for art in arts:
        a = Artifact(message_id=am.id, content=art['content'], language=art['language'], title=art['title'])
        db.session.add(a)
        saved_arts.append(a)
    db.session.commit()

    return jsonify({
        'message': {
            'id': am.id,
            'role': 'assistant',
            'content': answer,
            'created_at': am.created_at.isoformat()
        },
        'artifacts': [{'id': a.id, 'title': a.title, 'language': a.language, 'content': a.content} for a in saved_arts]
    })

# Artifacts
@api_bp.route('/artifacts', methods=['GET'])
@login_required
def list_artifacts():
    # join
    arts = db.session.query(Artifact).join(Message).join(Conversation).filter(Conversation.user_id==current_user.id).order_by(Artifact.created_at.desc()).limit(200).all()
    return jsonify([{
        'id': a.id,
        'title': a.title,
        'language': a.language,
        'content': a.content,
        'created_at': a.created_at.isoformat(),
        'message_id': a.message_id,
        'conversation_id': a.message.conversation_id if a.message else None
    } for a in arts])

@api_bp.route('/artifacts/<int:aid>', methods=['GET'])
@login_required
def get_artifact(aid):
    a = db.session.query(Artifact).join(Message).join(Conversation).filter(Artifact.id==aid, Conversation.user_id==current_user.id).first_or_404()
    return jsonify({
        'id': a.id,
        'title': a.title,
        'language': a.language,
        'content': a.content,
        'created_at': a.created_at.isoformat()
    })

# Projects
@api_bp.route('/projects', methods=['GET'])
@login_required
def list_projects():
    ps = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
    return jsonify([{'id': p.id, 'name': p.name, 'description': p.description, 'created_at': p.created_at.isoformat(), 'conversations_count': len(p.conversations)} for p in ps])

@api_bp.route('/projects', methods=['POST'])
@login_required
def create_project():
    data = request.get_json() or {}
    p = Project(user_id=current_user.id, name=data.get('name','Untitled')[:150], description=data.get('description',''))
    db.session.add(p)
    db.session.commit()
    return jsonify({'id': p.id, 'name': p.name, 'description': p.description}), 201

@api_bp.route('/projects/<int:pid>', methods=['PUT'])
@login_required
def update_project(pid):
    p = Project.query.filter_by(id=pid, user_id=current_user.id).first_or_404()
    data = request.get_json() or {}
    if 'name' in data: p.name = data['name'][:150]
    if 'description' in data: p.description = data['description']
    db.session.commit()
    return jsonify({'ok': True})

@api_bp.route('/projects/<int:pid>', methods=['DELETE'])
@login_required
def delete_project(pid):
    p = Project.query.filter_by(id=pid, user_id=current_user.id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    return jsonify({'ok': True})

@api_bp.route('/projects/<int:pid>/conversations', methods=['GET'])
@login_required
def project_conversations_list(pid):
    p = Project.query.filter_by(id=pid, user_id=current_user.id).first_or_404()
    return jsonify([to_dict_conv(c) for c in p.conversations])

@api_bp.route('/projects/<int:pid>/conversations', methods=['POST'])
@login_required
def project_add_conversation(pid):
    p = Project.query.filter_by(id=pid, user_id=current_user.id).first_or_404()
    data = request.get_json() or {}
    cid = data.get('conversation_id')
    c = Conversation.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    if c not in p.conversations:
        p.conversations.append(c)
        db.session.commit()
    return jsonify({'ok': True})

@api_bp.route('/projects/<int:pid>/conversations/<int:cid>', methods=['DELETE'])
@login_required
def project_remove_conversation(pid, cid):
    p = Project.query.filter_by(id=pid, user_id=current_user.id).first_or_404()
    c = Conversation.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    if c in p.conversations:
        p.conversations.remove(c)
        db.session.commit()
    return jsonify({'ok': True})

# Jobs
@api_bp.route('/jobs', methods=['GET'])
@login_required
def list_jobs():
    jobs = Job.query.filter_by(user_id=current_user.id).order_by(Job.created_at.desc()).all()
    return jsonify([{
        'id': j.id,
        'title': j.title,
        'description': j.description,
        'mcp_server': j.mcp_server,
        'prompt': j.prompt,
        'status': j.status,
        'result': j.result,
        'created_at': j.created_at.isoformat(),
        'completed_at': j.completed_at.isoformat() if j.completed_at else None
    } for j in jobs])

@api_bp.route('/jobs', methods=['POST'])
@login_required
def create_job():
    data = request.get_json() or {}
    j = Job(
        user_id=current_user.id,
        title=data.get('title','Claude Code Job')[:200],
        description=data.get('description',''),
        mcp_server=data.get('mcp_server',''),
        prompt=data.get('prompt',''),
        status='queued'
    )
    db.session.add(j)
    db.session.commit()
    # start async
    start_job_async(j.id, current_app._get_current_object())
    return jsonify({'id': j.id, 'status': j.status}), 201

@api_bp.route('/jobs/<int:jid>', methods=['GET'])
@login_required
def get_job(jid):
    j = Job.query.filter_by(id=jid, user_id=current_user.id).first_or_404()
    return jsonify({
        'id': j.id, 'title': j.title, 'status': j.status,
        'result': j.result, 'prompt': j.prompt
    })

@api_bp.route('/jobs/<int:jid>/status', methods=['GET'])
@login_required
def job_status(jid):
    j = Job.query.filter_by(id=jid, user_id=current_user.id).first_or_404()
    return jsonify({
        'id': j.id,
        'status': j.status,
        'result': j.result,
        'completed_at': j.completed_at.isoformat() if j.completed_at else None
    })

@api_bp.route('/jobs/<int:jid>', methods=['DELETE'])
@login_required
def delete_job(jid):
    j = Job.query.filter_by(id=jid, user_id=current_user.id).first_or_404()
    db.session.delete(j)
    db.session.commit()
    return jsonify({'ok': True})

# MCP servers
@api_bp.route('/mcp-servers', methods=['GET'])
@login_required
def list_mcp():
    servers = MCPServer.query.filter_by(is_active=True).all()
    return jsonify([s.to_dict() for s in servers])

@api_bp.route('/mcp-servers', methods=['POST'])
@login_required
def create_mcp():
    data = request.get_json() or {}
    s = MCPServer(
        name=data.get('name','MCP'),
        url=data.get('url',''),
        auth_token=data.get('auth_token',''),
        is_active=True
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201
