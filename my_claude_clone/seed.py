from models import db, User, Conversation, Message, Artifact, Project, Job, MCPServer
from datetime import datetime, timedelta

def seed_data():
    if User.query.first():
        print("Seed already exists, skip")
        return
    # user
    u = User(username='demo', email='demo@claude.com')
    u.set_password('123456')
    db.session.add(u)
    db.session.flush()

    # MCP server
    mcp = MCPServer(name='Claude Code Local', url='http://localhost:8000/mcp', auth_token='demo-token', is_active=True)
    db.session.add(mcp)

    # conversations
    convs = []
    titles = [
        'Python CSV парсер',
        'React dashboard с Tailwind',
        'Объясни MCP протокол',
        'Оптимизация SQL запросов'
    ]
    for t in titles:
        c = Conversation(user_id=u.id, title=t, created_at=datetime.utcnow()-timedelta(days=len(convs)))
        db.session.add(c)
        convs.append(c)
    db.session.flush()

    # messages + artifacts
    m1 = Message(conversation_id=convs[0].id, role='user', content='Напиши Python скрипт для парсинга CSV')
    db.session.add(m1); db.session.flush()
    m2 = Message(conversation_id=convs[0].id, role='assistant', content='Вот готовый скрипт:\n\n```python\nimport csv\n\nwith open("data.csv") as f:\n    reader = csv.DictReader(f)\n    for row in reader:\n        print(row)\n```')
    db.session.add(m2); db.session.flush()
    a1 = Artifact(message_id=m2.id, title='csv_parser.py', language='python', content='import csv\n\nwith open("data.csv") as f:\n    reader = csv.DictReader(f)\n    for row in reader:\n        print(row)')
    db.session.add(a1)

    m3 = Message(conversation_id=convs[1].id, role='user', content='Создай React компонент дашборда')
    db.session.add(m3); db.session.flush()
    m4 = Message(conversation_id=convs[1].id, role='assistant', content='Готово:\n\n```jsx\nexport default function Dashboard(){\n  return <div className="p-6">Hello Claude</div>\n}\n```')
    db.session.add(m4); db.session.flush()
    a2 = Artifact(message_id=m4.id, title='Dashboard.jsx', language='jsx', content='export default function Dashboard(){\n  return <div className="p-6">Hello Claude</div>\n}')
    db.session.add(a2)

    # projects
    p1 = Project(user_id=u.id, name='Web App 2025', description='Основной проект фронтенда на React + Tailwind')
    p2 = Project(user_id=u.id, name='Data Pipeline', description='ETL скрипты и MCP интеграции')
    db.session.add_all([p1,p2])
    db.session.flush()
    p1.conversations.append(convs[1])
    p1.conversations.append(convs[0])
    p2.conversations.append(convs[3])

    # job
    job = Job(user_id=u.id, title='Рефакторинг API', description='Автоматический рефакторинг через Claude Code', mcp_server='Claude Code Local', prompt='Refactor the REST API to FastAPI', status='completed', result='✅ Completed: 12 files changed, tests passed', completed_at=datetime.utcnow())
    db.session.add(job)

    db.session.commit()
    print("Seed done: demo@claude.com / 123456")
