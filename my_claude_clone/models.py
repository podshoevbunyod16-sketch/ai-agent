from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

# Many-to-many
project_conversations = db.Table('project_conversations',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('conversation_id', db.Integer, db.ForeignKey('conversation.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan')
    projects = db.relationship('Project', backref='user', lazy=True, cascade='all, delete-orphan')
    jobs = db.relationship('Job', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), default='Новый чат')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    is_favorite = db.Column(db.Boolean, default=False)

    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan', order_by='Message.created_at')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user / assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    artifacts = db.relationship('Artifact', backref='message', lazy=True, cascade='all, delete-orphan')

class Artifact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50), default='text')
    title = db.Column(db.String(200), default='Артефакт')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def conversation(self):
        return self.message.conversation if self.message else None

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversations = db.relationship('Conversation', secondary=project_conversations, 
        lazy='subquery',
        backref=db.backref('projects', lazy=True))

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    mcp_server = db.Column(db.String(200))
    prompt = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='queued')  # queued, running, completed, failed
    result = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class MCPServer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    auth_token = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'is_active': self.is_active
        }
